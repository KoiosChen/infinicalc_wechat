from app.models import Customers, MemberCards, ShopOrders, ItemsOrders
from app.common import success_return, false_return
from collections import defaultdict
from decimal import Decimal
from app.public_method import format_decimal


def customer_member_card(customer, member_type):
    customer_obj = Customers.query.get(customer) if isinstance(customer, str) else customer
    return customer_obj, customer_obj.member_card.filter_by(status=1, member_type=member_type).first()


def find_relationships(customer, member_type=1):
    """
    查找账号的邀请人，此事customer必须是代理商，因为只有代理商才会有邀请人。如果本人为二级，则查找一级，若是一级则不查找，返回本身的id
    :param customer: 可以是customers表的id，也可以是customer的对象实例
    :param action
    :param member_type
    :param level
    :return:
    """
    try:
        customer, member_card = customer_member_card(customer, member_type)
        if not customer:
            raise Exception("用户无效")
        relationship_dict = defaultdict(dict)
        relationship_dict['self']['id'] = customer.id
        if not member_card or member_card.member_type == 0:
            # 表明是直客, 直客没有invitor，invitor定义为代理商邀请人，这里只有interest_id
            # 如果有，则为其上游代理商的id
            relationship_dict['self']['grade'] = 0
            if customer.interest:
                # 利益关系上级
                relationship_dict['interest']['id'] = customer.interest.id
                relationship_dict['interest']['grade'] = customer.interest.member_card.filter_by(status=1,
                                                                                                 member_type=1).first().grade
                # 分享上级
                if customer.parent:
                    relationship_dict['parent']['id'] = customer.parent.id
                    relationship_dict['parent']['grade'] = customer.parent.member_card.filter_by(status=1,
                                                                                                 member_type=1).first().grade
                if relationship_dict['interest']['grade'] == 2:
                    # 如果自己的利益上级是2级代理，那么查找其一级代理
                    if not customer.interest.interest:
                        raise Exception(f"{customer.id} 此用户利益关系异常，无上级代理")
                    relationship_dict['interest']['interest'] = dict()
                    relationship_dict['interest']['interest']['id'] = customer.interest.interest.id
                    relationship_dict['interest']['interest']['grade'] = 1
                    # 利益上级的推荐人
                    if customer.interest.invitor:
                        relationship_dict['interest']['invitor'] = dict()
                        relationship_dict['interest']['invitor']['id'] = customer.interest.invitor.id
                        relationship_dict['interest']['invitor'][
                            'grade'] = customer.interest.invitor.member_card.filter_by(
                            status=1, member_type=1).first().grade
            else:
                # 如果当前用户是直客，那么没有invitor，说明他自己或者他的上级分享者没有上游代理商
                if customer.parent:
                    relationship_dict['parent']['id'] = customer.parent.id
                    relationship_dict['parent']['grade'] = 0
        elif member_card and member_type == 1:
            # 表明是代理商身份，代理商级别是1 或者2
            relationship_dict['self']['grade'] = member_card.grade
            if member_card.grade > 1:
                # 如果非一级代理商
                if not customer.interest:
                    raise Exception(f"{customer.id} 此用户利益关系异常，无上级代理")
                relationship_dict['interest']['id'] = customer.interest.id
                relationship_dict['interest']['grade'] = customer.interest.member_card.filter_by(status=1,
                                                                                                 member_type=1).first().grade
            if not customer.invitor:
                raise Exception(f"{customer.id} 此用户代理商邀请关系异常，无邀请人")
            relationship_dict['invitor']['id'] = customer.invitor.id

            # 判断当前客户的邀请人是否正常
            customer_invitor_member_card = customer.invitor.member_card.filter_by(status=1, member_type=1).first()
            if not customer_invitor_member_card or customer_invitor_member_card.member_type != 1:
                raise Exception(f"{customer.invitor.id} 的邀请人非代理商")
            relationship_dict['invitor']['grade'] = customer.invitor.member_card.filter_by(status=1,
                                                                                           member_type=1).first().grade
            if customer.parent:
                relationship_dict['parent']['id'] = customer.parent.id
                relationship_dict['parent']['grade'] = customer.parent.member_card.filter_by(status=1,
                                                                                             member_type=1).first().grade

        return success_return(data=relationship_dict)
    except Exception as e:
        return false_return(message=str(e)), 400


def calc(customer, shop_order_id):
    try:
        relationships = find_relationships(customer).get('data')
        shop_order = ShopOrders.query.filter_by(id=shop_order_id, customer_id=customer.id).first()
        if not shop_order:
            raise Exception(f"{customer.id} does not have shop order {shop_order_id}!")
        item_orders = shop_order.items_orders_id.filter_by(status=1, delete_at=None).all()
        if not item_orders:
            raise Exception(f"{shop_order_id} does not have item orders!")
        for item_order in item_orders:
            item_rebate_policy = item_order.bought_sku.rebate
            if relationships['self']['grade'] == 0:
                # 购买者是直客
                if 'interest' in relationships.keys():
                    # 直客有上级利益关系 - 有上级代理商
                    second_agent_rebate = Decimal('0.00')
                    invitor_rebate = Decimal('0.00')
                    if relationships['interest']['grade'] == 2:
                        second_agent_rebate = item_rebate_policy.agent_second_rebate
                        relationships['interest']['rebate'] = format_decimal(second_agent_rebate, to_str=True)
                        if 'invitor' in relationships['interest'].keys():
                            invitor_rebate = item_rebate_policy.agent_second_invitor_rebate
                            relationships['interest']['invitor']['rebate'] = format_decimal(invitor_rebate, to_str=True)
                        if 'interest' in relationships['interest'].keys():
                            if relationships['interest']['interest']['grade'] == 1:
                                relationships['interest']['interest'][
                                    'rebate'] = format_decimal(
                                    item_rebate_policy.agent_first_rebate - second_agent_rebate - invitor_rebate,
                                    to_str=True)
                            else:
                                raise Exception("级别错误，不进行计算返佣")
                    elif relationships['interest']['grade'] == 1:
                        relationships['interest']['rebate'] = format_decimal(item_rebate_policy.agent_first_rebate, to_str=True)
                if 'parent' in relationships.keys():
                    # 赠送积分给parent，如果rebate表里有数值
                    pass

            else:
                # 购买者是代理
                second_agent_rebate = Decimal('0.00')
                invitor_rebate = Decimal('0.00')
                if relationships['self']['grade'] == 2:
                    # 如果自己是二级代理，则先拿二级代理的佣金
                    second_agent_rebate = item_rebate_policy.agent_second_rebate
                    relationships['self']['rebate'] = format_decimal(second_agent_rebate, to_str=True)
                    if 'invitor' in relationships.keys():
                        invitor_rebate = item_rebate_policy.agent_second_invitor_rebate
                        relationships['invitor']['rebate'] = format_decimal(invitor_rebate, to_str=True)

                    if 'interest' in relationships.keys():
                        if relationships['interest']['grade'] == 1:
                            relationships['interest'][
                                'rebate'] = format_decimal(
                                item_rebate_policy.agent_first_rebate - second_agent_rebate - invitor_rebate,
                                to_str=True)
                        else:
                            raise Exception("级别错误，不进行计算返佣")
                elif relationships['self']['grade'] == 1:
                    relationships['self']['rebate'] = format_decimal(item_rebate_policy.agent_first_rebate, to_str=True)
        return success_return(data=relationships)
    except Exception as e:
        return false_return(str(e))
