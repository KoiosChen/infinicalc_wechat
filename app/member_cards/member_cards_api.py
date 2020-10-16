from flask_restplus import Resource, reqparse
from ..models import Permission, InvitationCode, MemberCards, MemberPolicies, MemberCardConsumption, \
    MemberRechargeRecords, make_uuid, make_order_id
from .. import db, default_api
from ..common import success_return, false_return, submit_return
from ..public_method import get_table_data, new_data_obj, create_member_card_num, query_coupon
import datetime
from app.decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
from app.wechat import pay

members_ns = default_api.namespace('member_cards', path='/member_cards', description='邀请码录入升级会员，会员信息查询')

return_json = members_ns.model('ReturnResult', return_dict)

member_cards_parser = page_parser.copy()

recharge_parser = page_parser.copy()
recharge_parser.add_argument("wechat_nickname", help='微信昵称，支持模糊查找', location='args')
recharge_parser.add_argument("phone_number", help='手机号，支持模糊查找', location='args')
recharge_parser.add_argument("start_at", type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d'),
                             help="充值范围，起始于，格式'%Y-%m-%d", location='args')
recharge_parser.add_argument("end_at", type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d'),
                             help="充值范围，结束于，格式'%Y-%m-%d", location='args')
recharge_parser.add_argument("member_card_id", help='会员号，支持模糊查找', location='args')

member_recharge_parser = reqparse.RequestParser()
member_recharge_parser.add_argument("amount", choices=[1, 1999, 4999, 9999, 29999], required=True, help='充值金额',
                                    type=int)


@members_ns.route("")
@members_ns.expect(head_parser)
class MemberCardsAPI(Resource):
    @members_ns.marshal_with(return_json)
    @members_ns.doc(body=member_cards_parser)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """
        若是前端账户查询，返回该用户所有会员卡，目前仅一张，去list[0]; 若是后端用户，显示所有用户
        """
        try:
            args = member_cards_parser.parse_args()
            if kwargs['current_user'].__class__.__name__ == 'Customers':
                args['search'] = {"customer_id": kwargs['current_user'].id, "status": 1, "delete_at": None}
            else:
                args['search'] = {"status": 1, "delete_at": None}
            return success_return(get_table_data(MemberCards, args, order_by="create_at"))
        except Exception as e:
            return false_return(message=str(e)), 400


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


@members_ns.route("/recharge")
@members_ns.expect(head_parser)
class MemberRecharge(Resource):
    @members_ns.marshal_with(return_json)
    @members_ns.doc(body=member_recharge_parser)
    @permission_required(Permission.USER)
    def post(self, **kwargs):
        """
        会员卡充值。 用户充值对应金额
        """
        try:
            args = member_recharge_parser.parse_args()
            current_user = kwargs['current_user']
            if current_user.member_type == 1:
                raise Exception("代理商不可充值")

            present_grade = current_user.member_grade
            recharge_amount = args.get('amount')
            if recharge_amount not in (1, 1999, 4999, 9999, 29999):
                raise Exception('充值金额不在规定范围内')

            current_card = current_user.card

            if not current_card:
                current_card = new_data_obj("MemberCards",
                                            **{"card_no": create_member_card_num(),
                                               "customer_id": current_user.id,
                                               "grade": 0})

                if not current_card or not current_card['status']:
                    raise Exception("create card fail")
                else:
                    current_card = current_card['obj']

            new_recharge_order = new_data_obj("MemberRechargeRecords",
                                              **{"id": make_order_id(),
                                                 "recharge_amount": recharge_amount,
                                                 "member_card": current_card.id})

            if not new_recharge_order or not new_recharge_order['status']:
                raise Exception("创建充值订单失败")

            return pay.weixin_pay(out_trade_no=new_recharge_order['obj'].id, price=recharge_amount,
                                  openid=current_user.openid, device_info="MemberRecharge")

        except Exception as e:
            return false_return(message=str(e))

    @members_ns.marshal_with(return_json)
    @permission_required([Permission.USER, "app.member_cards.member_cards_api.query_recharge"])
    def get(self, **kwargs):
        """
        若是后端用户获取所有用户充值记录， 可根据微信昵称，手机号，会员号，充值日期范围进行搜索
        若是前端用户，获取该用户充值记录（不可按照昵称等查询）
        """
        try:
            current_user = kwargs.get('current_user')
            if current_user.__class__.__name__ == "Users":
                pass
            else:
                member_card = current_user.member_card.first()
                return success_return(get_table_data(MemberRechargeRecords,
                                                     {},
                                                     advance_search=[{"key": "member_card",
                                                                      "operator": "__eq__",
                                                                      "value": member_card.id}],
                                                     order_by="create_at"))

        except Exception as e:
            return false_return(message=str(e)), 400


@members_ns.route("")
@members_ns.expect(head_parser)
class MemberRecharge(Resource):
    pass
