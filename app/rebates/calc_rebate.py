from app.models import Customers, MemberCards, ShopOrders, ItemsOrders, PersonalRebates, RETURN_IN_DAYS, make_uuid
from app.common import success_return, false_return
from collections import defaultdict
from decimal import Decimal
from app.public_method import new_data_obj, format_decimal
from app.common import submit_return
from app import logger
import datetime
import traceback


def customer_member_card(customer, member_type):
    customer_obj = Customers.query.get(customer) if isinstance(customer, str) else customer
    return customer_obj, customer_obj.member_card.filter_by(status=1, member_type=member_type).first()


def find_relationships(customer, member_type=1):
    """
    查找账号的邀请人，此customer必须是代理商，因为只有代理商才会有邀请人。如果本人为二级，则查找一级，若是一级则不查找，返回本身的id
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
        return false_return(message=str(e))


def checkout_rebates_ratio(customer, shop_order_id):
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
                        relationships['interest']['rebate'] = format_decimal(item_rebate_policy.agent_first_rebate,
                                                                             to_str=True)
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
        traceback.print_exc()
        return false_return(str(e))


def calc(shop_order_id, customer):
    def newPersonalRebates(rebate_relation_id, relation_):
        if 'rebate' in detail.keys() or 'score' in detail.keys():
            new_personal_rebate = new_data_obj('PersonalRebates',
                                               **{'shop_order_id': shop_order_id,
                                                  'customer_id': rebate_relation_id,
                                                  "relation": relation_,
                                                  'rebate': detail.get('rebate', 0.00),
                                                  'score': detail.get('score', 0)})
            if not new_personal_rebate or not new_personal_rebate.get('status'):
                logger.error('it is fail to create new personal rebate record')

    try:
        rebate_ratio = checkout_rebates_ratio(customer, shop_order_id)
        if rebate_ratio.get('code') != 'success':
            raise Exception('获取返佣比例失败')
        for relation, detail in rebate_ratio['data'].items():
            newPersonalRebates(detail.get('id'), relation)
            for key in ('interest', 'invitor', 'parent'):
                if key in detail.keys():
                    newPersonalRebates(detail.get('id'), relation + ":" + key)
        return submit_return('记录订单返佣成功', '记录订单返佣失败')
    except Exception as e:
        return false_return(message=str(e))


def self_rebate(customer):
    frozen_rebate = Decimal("0.00")
    current_rebate = Decimal("0.00")
    frozen_count = 0
    current_count = 0
    percent = Decimal('0.01')
    all_rebates = PersonalRebates.query.filter(PersonalRebates.customer_id.__eq__(customer.id)).all()
    for r in all_rebates:
        if r.related_order.is_pay == 1 and r.related_order.status == 1 and not r.related_order.delete_at:
            if r.rebate:
                if datetime.datetime.now() - r.create_at >= datetime.timedelta(days=7):
                    current_rebate += r.related_order.cash_fee * r.rebate * percent
                    current_rebate += 1
                else:
                    frozen_count += 1
                    frozen_rebate += r.related_order.cash_fee * r.rebate * percent

    return {"frozen_rebate": format_decimal(frozen_rebate, zero_format="0.00", to_str=True),
            "frozen_count": frozen_count,
            "current_rebate": format_decimal(current_rebate, zero_format="0.00", to_str=True),
            "current_count": current_count,
            "total_rebate": format_decimal(frozen_rebate + current_rebate, zero_format="0.00", to_str=True),
            "agents": len(customer.be_invited),
            "clients": len(set(customer.children) - set(customer.be_invited))}
