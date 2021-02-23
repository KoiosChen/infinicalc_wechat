from .scene_invitation_api import *
from app.models import BusinessUnitEmployees


@scene_invite_ns.route('/bu_invitation_qrcode')
@scene_invite_ns.expect(head_parser)
class BUInvitationApi(Resource):
    @scene_invite_ns.marshal_with(return_json)
    @permission_required(Permission.BU_OPERATOR)
    def get(self, **kwargs):
        """
        店铺员工生成二维码（永久），供用户扫码
        """
        current_user = kwargs['current_user']
        if current_user.business_unit_employee.status.delete_at is None:
            redis_db.set(current_user.id, current_user.business_unit_employee.id)
            redis_db.expire(current_user.id, 600)
            return success_return(data={'scene': 'new_customer', 'scene_invitation': current_user.id})
        else:
            return false_return(message="不可生成二维码"), 400