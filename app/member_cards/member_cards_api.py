from flask import request
from flask_restplus import Resource, reqparse
from ..models import Customers, Permission, ExpressAddress, InvitationCode, MemberCards
from . import member_cards
from app.frontstage_auth import auths
from .. import db, default_api, logger
from ..common import success_return, false_return, submit_return
from ..public_method import table_fields, get_table_data, get_table_data_by_id, new_data_obj
import datetime
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
import random

members_ns = default_api.namespace('member_cards', path='/member_cards', description='邀请码录入升级会员，会员信息查询')

return_json = members_ns.model('ReturnResult', return_dict)


def create_member_card_num():
    today = datetime.datetime.now()
    return "5199" + str(today.year) + str(today.month).zfill(2) + str(today.day).zfill(2) + str(
        random.randint(1000, 9999))


member_cards_parser = page_parser.copy()


@members_ns.route("")
@members_ns.expect(head_parser)
class MemberCards(Resource):
    @members_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """
        提交邀请码，升级用户类型
        """
        return success_return(get_table_data(MemberCards))


@members_ns.route("/<string:invitation_code>")
@members_ns.expect(head_parser)
@members_ns.param("invitation_code", "邀请码")
class InviteToBeMember(Resource):
    @members_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def post(self, **kwargs):
        """
        提交邀请码，升级用户类型。若原先没有会员卡，升级成功后会自动生成一张会员卡，且等级为邀请码对应的等级
        """
        current_user = kwargs['current_user']
        today = datetime.datetime.now()
        invitation_code = InvitationCode.query.filter(InvitationCode.code == kwargs['invitation_code'],
                                                      InvitationCode.used_at.__eq__(None),
                                                      InvitationCode.validity_at.__ge__(today)).first()

        if not invitation_code:
            return false_return(message="邀请码无效"), 400

        member_card = current_user.member_card.first()

        # 此处目前仅支持邀请代理商
        if member_card and int(member_card.member_type) >= int(invitation_code.tobe_type) and int(
                member_card.grade) <= int(invitation_code.tobe_level):
            return false_return(message="当前用户已经是此级别(或更高级别），不可使用此邀请码"), 400

        invitor_grade = 1  # how to set the params

        if not member_card:
            card_no = create_member_card_num()
            new_member_card = new_data_obj("MemberCards", **{"card_no": card_no, "customer_id": current_user.id})
        else:
            card_no = member_card.card_no
            new_member_card = {'obj': member_card, 'status': False}

        a = {"member_type": invitation_code.tobe_type,
             "grade": invitation_code.tobe_level,
             "invitor_id": invitation_code.manager_customer_id,
             "invitor_grade": invitor_grade,
             "validate_date": datetime.datetime.now() + datetime.timedelta(days=365)}

        if new_member_card['status']:
            a['open_date'] = datetime.datetime.now()
            a['card_no'] = card_no

        for k, v in a.items():
            setattr(new_member_card['obj'], k, v)

        if new_member_card:
            invitation_code.used_customer_id = current_user.id
            invitation_code.new_member_card_id = new_member_card['obj'].id
            db.session.add(invitation_code)
        else:
            return false_return(message="邀请码有效，但是新增会员卡失败"), 400

        return submit_return(f"新增会员卡成功，卡号{card_no}, 会员级别{invitation_code.tobe_type} {invitation_code.tobe_level}",
                             "新增会员卡失败")
