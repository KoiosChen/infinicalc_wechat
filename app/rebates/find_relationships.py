from app.models import Customers, MemberCards
from app.common import success_return, false_return
from collections import defaultdict


def customer_member_card(customer, member_type):
    customer_obj = Customers.query.get(customer) if isinstance(customer, str) else customer
    return customer_obj, customer_obj.member_card.filter_by(status=1, member_type=member_type).first()


def find_rebate_relationships(customer, member_type=1):
    """
    查找账号的邀请人，此事customer必须是代理商，因为只有代理商才会有邀请人。如果本人为二级，则查找一级，若是一级则不查找，返回本身的id
    :param customer: 可以是customers表的id，也可以是customer的对象实例
    :param action
    :param member_type
    :param level
    :return:
    """
    customer, member_card = customer_member_card(customer, member_type)
    if not customer:
        false_return(message="用户无效")
    relationship_dict = defaultdict(dict)
    if not member_card or member_card.member_type == 0:
        # 表明是直客, 直客没有invitor，invitor定义为代理商邀请人，这里只有interest_id
        # 如果有，则为其上游代理商的id
        if customer.interest:
            # 利益关系上级
            relationship_dict['interest']['id'] = customer.interest.id
            relationship_dict['interest']['grade'] = customer.interest.member_card.filter_by(status=1,
                                                                                             member_type=1).first().grade
            # 分享上级
            if customer.parent:
                relationship_dict['parent']['id'] = customer.parent.id
                relationship_dict['parent']['grade'] = customer.parent.member_card.filter_by(status=1, member_type=1).first().grade
            if relationship_dict['interest']['grade'] == 2:
                # 如果自己的利益上级是2级代理，那么查找其一级代理
                if not customer.interest.interest:
                    return false_return(message=f"{customer.id} 此用户利益关系异常，无上级代理")
                relationship_dict['grand_interest']['id'] = customer.interest.interest.id
                relationship_dict['grand_interest']['grade'] = 1
                # 利益上级的推荐人
                if customer.interest.invitor:
                    relationship_dict['interest_invitor']['id'] = customer.interest.invitor.id
                    relationship_dict['interest_invitor']['grade'] = customer.interest.invitor.member_card.filter_by(
                        status=1, member_type=1).first().grade
        else:
            # 如果当前用户是直客，那么没有invitor，说明他自己或者他的上级分享者没有上游代理商
            if customer.parent:
                relationship_dict['parent']['id'] = customer.parent.id
                relationship_dict['parent']['grade'] = 0
    elif member_card and member_type == 1:
        # 表明是代理商身份，代理商级别是1 或者2
        if member_card.grade > 1:
            # 如果非一级代理商
            if not customer.interest:
                return false_return(message=f"{customer.id} 此用户利益关系异常，无上级代理")
            relationship_dict['interest']['id'] = customer.interest.id
            relationship_dict['interest']['grade'] = customer.interest.member_card.filter_by(status=1,
                                                                                             member_type=1).first().grade
        if not customer.invitor:
            return false_return(message=f"{customer.id} 此用户代理商邀请关系异常，无邀请人")
        relationship_dict['invitor']['id'] = customer.invitor.id
        relationship_dict['invitor']['grade'] = customer.invitor.member_card.filter_by(status=1,
                                                                                       member_type=1).first().grade
        if customer.parent:
            relationship_dict['parent']['id'] = customer.parent.id
            relationship_dict['parent']['grade'] = customer.parent.member_card.filter_by(status=1,
                                                                                         member_type=1).first().grade

    return success_return(data=relationship_dict)


if __name__ == "__main__":
    find_rebate_relationships("7b39aa04-dbb5-4c51-a833-26976cff67fb")