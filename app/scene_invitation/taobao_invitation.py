from .scene_invitation_api import *
from app.models import BusinessUnitEmployees

qrcode_parser = reqparse.RequestParser()
qrcode_parser.add_argument('obj_id', required=True, type=str, help='对象ID， 例如加盟商ID， 店铺ID，员工ID', location='args')
qrcode_parser.add_argument('scene', required=True, type=str, help='例如，新增加盟商时返回的key是new_franchisee', location='args')


@scene_invite_ns.route('/taobao_qrcode')
@scene_invite_ns.expect(head_parser)
class TaobaoInvitationApi(Resource):
    @scene_invite_ns.marshal_with(return_json)
    @scene_invite_ns.doc(body=qrcode_parser)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """
        新小程序邀请码生成接口
        """
        args = qrcode_parser.parse_args()
        scene_invitation = generate_code(12)
        redis_db.set(scene_invitation, args['obj_id'])
        redis_db.expire(scene_invitation, 600)
        return success_return(data={'scene': args['scene'], 'scene_invitation': scene_invitation})
