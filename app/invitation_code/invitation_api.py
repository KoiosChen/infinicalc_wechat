from flask_restplus import Resource, fields, reqparse
from ..models import Layout, SKULayout, SKU, InvitationCode, Permission
from . import invitation_code
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import table_fields, new_data_obj, get_table_data
from ..decorators import permission_required
from ..swagger import head_parser, return_dict, page_parser
import random
import string
import datetime

invite_ns = default_api.namespace('Invitation Code', path='/invitation_code', description='邀请码，可邀请成为代理商或者会员用户')

return_json = invite_ns.model('ReturnRegister', return_dict)

invitation_parser = reqparse.RequestParser()
invitation_parser.add_argument('tobe_type', type=int, choices=[0, 1], default=1, required=True,
                               help='不传默认为1，表示代理商； 0 表示会员用户')
invitation_parser.add_argument('tobe_level', type=int, required=True, choices=[1, 2],
                               help='目前仅邀请成为代理商，tobe_type传1；此处传1，表示一级代理商，传2 表示二级代理商。')
invitation_parser.add_argument('number', type=int, default=1, required=True, help='生成数量')
invitation_parser.add_argument('manager_customer_id', required=True,
                               help='邀请码生成后在哪个customers.id下能够显示, 被邀请人的invitor_id写入此字段 - 如果没有邀请人，则使用公司市场部ID，归属公司总部。')
invitation_parser.add_argument('interest_customer_id', required=True,
                               help='被邀请人填入邀请码之后，其interest_id字段将写入此customers.id - 如果没有邀请人，则使用公司市场部ID，归属公司总部。')
invitation_parser.add_argument('validity_days', help='有效天数，从生成日算起', type=int, default=30)

invite_page_parser = page_parser.copy()


def generate_code(code_len=8):
    seed = "1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    sa = []
    for i in range(code_len):
        sa.append(random.choice(seed))
    salt = ''.join(sa)
    return salt


@invite_ns.route('')
@invite_ns.expect(head_parser)
class InvitationApi(Resource):
    @invite_ns.marshal_with(return_json)
    @invite_ns.doc(body=invite_page_parser)
    @permission_required([Permission.USER, "app.invitation_code.query_all"])
    def get(self, **kwargs):
        """
        获取所有邀请码
        """
        args = invite_page_parser.parse_args()
        # 如果是前端客户，则只显示本人管理的邀请码，且只显示有效的
        if kwargs.get('current_user') and kwargs['current_user'].__class__.__name__ == 'Customers':
            args['search'] = {"manager_customer_id": kwargs['current_user'].id,
                              "validity_at": datetime.datetime.now(),
                              "used_at": None}
        return success_return(get_table_data(InvitationCode, args))

    @invite_ns.doc(body=invitation_parser)
    @invite_ns.marshal_with(return_json)
    @permission_required("app.invitation_code.generate_codes")
    def post(self, **kwargs):
        """生成邀请码"""
        args = invitation_parser.parse_args()
        number = args.pop('number')
        validity_days = args.pop('validity_days')

        params = {k: v for k, v in args.items() if v}

        params['validity_at'] = datetime.datetime.now() + datetime.timedelta(days=validity_days)
        if kwargs.get('current_user'):
            params['creator_id'] = kwargs['current_user'].id
        for _ in range(0, number):
            flag = True
            while flag:
                code_ = generate_code()
                if not InvitationCode.query.filter(InvitationCode.code == code_).first():
                    params['code'] = code_
                    new_invitation = new_data_obj("InvitationCode", **params)
                    if not new_invitation:
                        return false_return(message="生成邀请码失败")
                    flag = False

        return submit_return(f"共添加{number}个邀请码给用户ID<{args['manager_customer_id']}>", "新增邀请码失败")
