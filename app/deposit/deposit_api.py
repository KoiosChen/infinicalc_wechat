from flask_restplus import Resource, reqparse
from ..models import ShopOrders, Permission, ItemsOrders, Refund, make_uuid, Deposit
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
from app.type_validation import checkout_sku_type
from ..wechat.pay import weixin_pay
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
        return success_return(data=get_table_data(Deposit, args, appends=['objects']))

    @deposit_ns.marshal_with(return_json)
    @deposit_ns.doc(body=deposit_parser)
    @permission_required(Permission.USER)
    def post(self, **kwargs):
