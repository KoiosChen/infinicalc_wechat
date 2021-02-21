from .scene_invitation_api import *
from app.models import BusinessUnitEmployees


@scene_invite_ns.route('/bu_invitation_qrcode')
@scene_invite_ns.expect(head_parser)
class BUInvitationApi(Resource):
    @scene_invite_ns.marshal_with(return_json)
    @permission_required(Permission.BU_OPERATOR)
    def get(self, **kwargs):
        """
        店铺员工生成二维码（永久），供
        """
        current_user = kwargs['current_user']
        if current_user.business_unit_employee.status.delete_at is None:
            return success_return(data={"customer_id": current_user.id,
                                        "employee_id": current_user.business_unit_employee.id}
                                  )
        else:
            return false_return(message="此员工已注销，不可生成二维码")


@scene_invite_ns.route('/bu_invitation_verify/<string:customer_id>/<string:employee_id>')
@scene_invite_ns.expect(head_parser)
class BUInvitationVerify(Resource):
    @scene_invite_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def post(self, **kwargs):
        """
        客户扫码的入口，验证后invitor写入这个店员的
        """
        customer_id = kwargs['customer_id']
        employee_id = kwargs['employee_id']
        current_user = kwargs['current_user']
        if current_user.bu_id or current_user.bu_employee_id:
            return false_return(message='用户已有归属店铺')
        else:
            current_user.bu_employee_id = employee_id

            bu_employee_obj = BusinessUnitEmployees.query.get(employee_id)
            if bu_employee_obj.customer_id != customer_id:
                return false_return(message="参数不付")
            else:
                current_user.bu_id = bu_employee_obj.business_unit_id
                return submit_return('success', 'fail')
