from flask_restplus import Resource
from ..models import Permission, InvitationCode, MemberCards
from .. import db, default_api
from ..common import success_return, false_return, submit_return
from ..public_method import get_table_data, new_data_obj, create_member_card_num
import datetime
from app.decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser

members_ns = default_api.namespace('member_cards', path='/member_cards', description='邀请码录入升级会员，会员信息查询')

return_json = members_ns.model('ReturnResult', return_dict)

member_cards_parser = page_parser.copy()


@members_ns.route("")
@members_ns.expect(head_parser)
class MemberCardsAPI(Resource):
    @members_ns.marshal_with(return_json)
    @members_ns.doc(body=member_cards_parser)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """
        提交邀请码，升级用户类型
        """
        args = member_cards_parser.parse_args()
        args['search'] = {"customer_id": kwargs['current_user'].id, "status": 1, "delete_at": None}
        return success_return(get_table_data(MemberCards, args))


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
        invitation_code = InvitationCode.query.filter(InvitationCode.code.__eq__(kwargs['invitation_code']),
                                                      InvitationCode.used_at.__eq__(None),
                                                      InvitationCode.validity_at.__ge__(today)).first()

        if not invitation_code:
            return false_return(message="邀请码无效"), 400

        member_card = current_user.member_card.first()

        # 此处目前仅支持邀请代理商
        if member_card and int(member_card.member_type) >= int(invitation_code.tobe_type) and int(
                member_card.grade) <= int(invitation_code.tobe_level):
            return false_return(message="当前用户已经是此级别(或更高级别），不可使用此邀请码"), 400

        if not member_card:
            card_no = create_member_card_num()
            new_member_card = new_data_obj("MemberCards", **{"card_no": card_no, "customer_id": current_user.id,
                                                             "open_date": datetime.datetime.now()})
        else:
            card_no = member_card.card_no
            new_member_card = {'obj': member_card, 'status': False}

        a = {"member_type": invitation_code.tobe_type,
             "grade": invitation_code.tobe_level,
             "validate_date": datetime.datetime.now() + datetime.timedelta(days=365)}

        for k, v in a.items():
            setattr(new_member_card['obj'], k, v)

        if new_member_card:
            invitation_code.used_customer_id = current_user.id
            invitation_code.new_member_card_id = new_member_card['obj'].id
            invitation_code.used_at = datetime.datetime.now()
            current_user.invitor_id = invitation_code.manager_customer_id
            current_user.interest_id = invitation_code.interest_customer_id
            db.session.add(invitation_code)
            db.session.add(current_user)
        else:
            return false_return(message="邀请码有效，但是新增会员卡失败"), 400

        return submit_return(f"新增会员卡成功，卡号{card_no}, 会员级别{invitation_code.tobe_type} {invitation_code.tobe_level}",
                             "新增会员卡失败")
