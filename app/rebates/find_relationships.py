from app.models import Customers, MemberCards
from app.common import success_return, false_return
from collections import defaultdict


def customer_member_card(customer, member_type):
    customer_obj = Customers.query.get(customer) if isinstance(customer, str) else customer
    return customer_obj, customer_obj.member_card.filter_by(status=1, member_type=member_type).first()


def find_rebate_relationships(customer, action="parent", member_type=1, level=1):
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
        # 表明是直客, 直客只要找他的invitor是否有值，
        # 如果有，则为其上游代理商的id
        if customer.invitor:
            relationship_dict['invitor']['id'] = customer.invitor.id
            relationship_dict['invitor']['grade'] = customer.member_card.filter_by(status=1, member_type=1).first().grade
            relationship_dict['parent']['id'] = customer.parent.id
            relationship_dict['parent']['grade'] = customer.member_card.filter_by(status=1, member_type=1).first().grade
            if relationship_dict['invitor']['grade'] == 2:
                relationship_dict['grand_invitor']['id'] = customer.invitor.invitor.id
                relationship_dict['grand_invitor']['grade'] = 1
                relationship_dict['invitor_parent']['id'] = customer.parent.id
                relationship_dict['invitor_parent']['grade'] = customer.parent.member_card.filter_by(status=1, member_type=1).first().grade
        else:
            # 如果当前用户是直客，那么没有invitor，说明他自己或者他的上级分享者没有上游代理商
            if customer.parent:
                relationship_dict['parent']['id'] = customer.parent.id
                relationship_dict['parent']['grade'] = 0
    elif member_card and member_type == 1:
        # 表明是代理商身份，代理商级别是1 或者2
        if member_card.grade == 1:
            pass
            # 如果是一级代理商，则返回空的relation_dict

        else:
            # 如果是二级代理商
            relationship_dict['invitor']['id'] = customer.invitor.id
            relationship_dict['invitor']['grade'] = 1
            relationship_dict['parent']['id'] = customer.parent.id
            relationship_dict['parent']['grade'] = customer.parent.member_card.filter_by(status=1, member_type=1).first().grade

    return success_return(data=relationship_dict)
