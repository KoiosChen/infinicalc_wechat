from flask_restplus import Resource, fields, reqparse
from ..models import Layout, SKULayout, SKU, InvitationCode, Permission, SceneInvitation
from . import scene_invitation
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import table_fields, new_data_obj, get_table_data
from ..decorators import permission_required
from ..swagger import head_parser, return_dict, page_parser
import random
import string
import datetime
from sqlalchemy import or_
import traceback
import datetime

scene_invite_ns = default_api.namespace('Scene Invitation', path='/scene_invitation', description='场景邀请码自助生成')

return_json = scene_invite_ns.model('ReturnRegister', return_dict)

invitation_parser = reqparse.RequestParser()
invitation_parser.add_argument('name', type=str, help='邀请码名称，例如“西安路演邀请码”')
invitation_parser.add_argument('max_invitees', type=int, default=0, help='最大允许接入的被邀请人， 0表示没有限制,')
invitation_parser.add_argument('start_at', type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d %H:%M:%S'),
                               help='有效开始时间-"%Y-%m-%d %H:%M:%S"')
invitation_parser.add_argument('end_at', type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d %H:%M:%S'),
                               help='有效结束时间-"%Y-%m-%d %H:%M:%S"')

invite_page_parser = page_parser.copy()


def generate_code(code_len=8):
    seed = "1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    sa = []
    for i in range(code_len):
        sa.append(random.choice(seed))
    salt = ''.join(sa)
    return salt


@scene_invite_ns.route('')
@scene_invite_ns.expect(head_parser)
class SceneInvitationApi(Resource):
    @scene_invite_ns.marshal_with(return_json)
    @scene_invite_ns.doc(body=invite_page_parser)
    @permission_required(Permission.MEMBER)
    def get(self, **kwargs):
        """
        获取本人所有场景邀请码
        """
        args = invite_page_parser.parse_args()
        # 如果是前端客户，则只显示本人管理的邀请码，且只显示有效的
        if kwargs.get('current_user') and kwargs['current_user'].__class__.__name__ == 'Customers':
            args['search'] = {"manager_customer_id": kwargs['current_user'].id}
        invite_qrcode = get_table_data(SceneInvitation, args, ['my_invitees'])
        return_result = list()
        for qr in invite_qrcode["records"]:
            max_check = qr['max_invitees'] > qr['my_invitees']
            validate_time = datetime.datetime.strptime(qr['start_at'], "%Y-%m-%d %H:%M:%S") <= datetime.datetime.now() <= datetime.datetime.strptime(qr['end_at'], "%Y-%m-%d %H:%M:%S")
            if max_check and validate_time:
                return_result.append(qr)
        return success_return(return_result)

    @scene_invite_ns.doc(body=invitation_parser)
    @scene_invite_ns.marshal_with(return_json)
    @permission_required(Permission.MEMBER)
    def post(self, **kwargs):
        """生成邀请码"""
        try:
            args = invitation_parser.parse_args()

            params = {k: v for k, v in args.items() if v}
            if not params:
                params['name'] = f"一次性邀请码（{datetime.datetime.now()}）"
                params['start_at'] = datetime.datetime.now()
                params['end_at'] = datetime.datetime.now() + datetime.timedelta(hours=24)
                params['max_invitees'] = 1

            params['tobe_type'] = 1
            params['tobe_level'] = 2

            if kwargs.get('current_user'):
                params['manager_customer_id'] = kwargs['current_user'].id
                user_grade = kwargs.get('current_user').grade
                if user_grade == 0:
                    raise Exception("此用户为直客，不可邀请代理商")
                elif user_grade == 1:
                    params['interest_customer_id'] = kwargs['current_user'].id
                elif user_grade == 2:
                    params['interest_customer_id'] = kwargs['current_user'].interest_id
            if SceneInvitation.query.filter(SceneInvitation.name.__eq__(args['name'])).first():
                raise Exception("邀请码名称重复")
            flag = True
            while flag:
                code_ = generate_code()
                if not SceneInvitation.query.filter(SceneInvitation.code.__eq__(code_)).first():
                    params['code'] = code_
                    new_invitation = new_data_obj("SceneInvitation", **params)
                    if not new_invitation:
                        raise Exception("生成邀请码失败")
                    flag = False
            return submit_return(f"添加场景邀请码{params['name']}成功", "新增邀请码失败")
        except Exception as e:
            traceback.print_exc()
            return false_return(message=str(e)), 400
