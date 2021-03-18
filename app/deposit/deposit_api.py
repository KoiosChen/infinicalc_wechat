from flask_restplus import Resource, reqparse
from ..models import ShopOrders, Permission, ItemsOrders, Refund, make_uuid, Deposit
from .. import db, redis_db, default_api, logger, image_operate
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
from app.type_validation import checkout_sku_type
from ..wechat.pay import weixin_pay
from app.scene_invitation.scene_invitation_api import generate_code
import datetime

deposit_ns = default_api.namespace('Deposit', path='/deposit', description='存酒接口')

return_json = deposit_ns.model('ReturnRegister', return_dict)

get_deposit_order = page_parser.copy()
get_deposit_order.add_argument('deposit_person', required=False, tyep=str, help='寄存人id， 如果为空，则按照调用接口的用户id来查询',
                               location='args')
get_deposit_order.add_argument('deposit_status', required=False, help='0,查询开瓶的； 1查询未开瓶的', location='args')
get_deposit_order.add_argument('deposit_confirm_waiter', required=False, help='操作寄存的服务员ID', location='args')
get_deposit_order.add_argument('deposit_bu_id', required=False, help='寄存的店铺', location='args')
get_deposit_order.add_argument('deposit_confirm_at', required=False,
                               type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d'),
                               help="寄存确认时间，格式'%Y-%m-%d", location='args')
get_deposit_order.add_argument('pickup_waiter', required=False, help='取酒员工ID', location='args')
get_deposit_order.add_argument('pickup_at', required=False, type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d'),
                               help="取酒时间，格式'%Y-%m-%d", location='args')

deposit_parser = reqparse.RequestParser()
deposit_parser.add_argument("sku_id", required=True, type=str, help='需要寄存酒的SKU')
deposit_parser.add_argument('objects', type=list, help='寄存酒的照片', location='json')
deposit_parser.add_argument("deposit_status", required=True, type=int, help='0，已开瓶；1 ，未开瓶')


@deposit_ns.route('')
@deposit_ns.expect(head_parser)
class GetAllDepositOrders(Resource):
    @deposit_ns.marshal_with(return_json)
    @deposit_ns.doc(body=get_deposit_order)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """获取用户所有寄存订单"""
        args = get_deposit_order.parse_args()
        args['search'] = dict()
        search_key = (
            "deposit_person",
            "deposit_status",
            "deposit_confirm_waiter",
            "deposit_bu_id",
            "deposit_confirm_at",
            "pickup_waiter",
            "pickup_at"
        )
        for key in search_key:
            if key in args.keys():
                args['search'][key] = args[args[key]]
        current_user = kwargs['current_user']
        if not args['search']["deposit_person"]:
            args['search']['deposit_person'] = current_user.id
        args['search']['delete_at'] = None
        return success_return(data=get_table_data(Deposit, args, appends=['objects']))

    @deposit_ns.marshal_with(return_json)
    @deposit_ns.doc(body=deposit_parser)
    @permission_required(Permission.USER)
    def post(self, **kwargs):
        args = deposit_parser.parse_args()
        sku_id = args['sku_id']
        deposit_status = args['deposit_status']
        deposit_id = make_uuid()
        new_deposit = new_data_obj("Deposit", **{"id": deposit_id,
                                                 "sku_id": sku_id,
                                                 "deposit_status": deposit_status,
                                                 "deposit_person": kwargs['current_user'].id})

        if not new_deposit:
            return false_return(message="寄存失败"), 400

        image_operate.operate(obj=new_deposit['obj'], imgs=args['objects'], action="append")

        if session_commit().get("code") == "success":
            qrcode = generate_code(12)
            redis_db.set(qrcode, deposit_id)
            redis_db.expire(qrcode, 120)
            return success_return(data=qrcode)
        else:
            return false_return(message='寄存失败'), 400


@deposit_ns.route('/verification/<string:qrcode>')
@deposit_ns.expect(head_parser)
class VerifyDeposit(Resource):
    @deposit_ns.marshal_with(return_json)
    @permission_required(Permission.BU_WAITER)
    def post(self, **kwargs):
        """服务员核销用户寄存订单，表示确认寄存"""
        employee_obj = kwargs['current_user'].business_unit_employee
        business_unit = employee_obj.business_unit
        qrcode = kwargs['qrcode']
        if not redis_db.exists(qrcode):
            return false_return(message=f'{qrcode} 不存在或超时，请客户查找寄存订单重新生成核销码'), 400

        deposit_id = redis_db.get(qrcode)
        redis_db.delete(qrcode)
        deposit_obj = Deposit.query.filter(Deposit.id.__eq__(deposit_id), Deposit.delete_at.__eq__(None),
                                           Deposit.deposit_bu_id.__eq__(None),
                                           Deposit.deposit_confirm_waiter.__eq__(None)).first()
        if not deposit_obj:
            return false_return(message='寄存订单无效，不可核销')

        deposit_obj.deposit_confirm_waiter = kwargs['current_user'].id
        deposit_obj.deposit_bu_id = business_unit.id
        deposit_obj.deposit_confirm_at = datetime.datetime.now()
        return submit_return('寄存核销成功', '寄存核销失败')


@deposit_ns.route('/pickup/<string:deposit_id>')
@deposit_ns.expect(head_parser)
class PickupDeposit(Resource):
    @deposit_ns.marshal_with(return_json)
    @deposit_ns.doc(body=deposit_parser)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """用户取寄存的酒，产生取酒的二维码"""
        qrcode = generate_code(12)
        redis_db.set(qrcode, kwargs['deposit_id'])
        redis_db.expire(qrcode, 60)
        return success_return(data=qrcode)

    @deposit_ns.marshal_with(return_json)
    @deposit_ns.doc(body=deposit_parser)
    @permission_required(Permission.USER)
    def post(self, **kwargs):
        pass