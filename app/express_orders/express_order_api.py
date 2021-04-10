from flask_restplus import Resource, reqparse, cors
from flask import request
from ..models import Permission, CloudWineExpressAddress, CloudWineExpressOrders, SKU, make_uuid
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, sort_by_order, submit_return
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id
from ..decorators import permission_required, allow_cross_domain
from ..swagger import return_dict, head_parser, page_parser
import datetime

express_ns = default_api.namespace('cloudwine_express', path='/cloudwine_express', description='客户发货申请及相关确认接口')

return_json = express_ns.model('ReturnRegister', return_dict)

express_order_page_parser = page_parser.copy()

new_express_order_parser = reqparse.RequestParser()
new_express_order_parser.add_argument("recipient_id", required=True, help='收件人地址的id，cloudwine_express_address表的id')
new_express_order_parser.add_argument("sku_id", required=True, help='发货的sku id')
new_express_order_parser.add_argument("quantity", required=True, help='发货数量')


@express_ns.route('')
@express_ns.expect(head_parser)
class ExpressOrderAPI(Resource):
    @express_ns.marshal_with(return_json)
    @express_ns.doc(body=express_order_page_parser)
    @permission_required([Permission.USER, "app.express_orders.express_order_api.ExpressOrderAPI.get"])
    def get(self, **kwargs):
        """查询所有快递订单列表"""
        args = express_order_page_parser.parse_args()
        return success_return(get_table_data(CloudWineExpressOrders, args), "请求成功")

    @express_ns.marshal_with(return_json)
    @express_ns.doc(body=new_express_order_parser)
    @permission_required([Permission.USER, "app.express_orders.express_order_api.ExpressOrderAPI.post"])
    def post(self, **kwargs):
        """新建快递订单"""
        try:
            args = new_express_order_parser.parse_args()
            recipient_id = args['recipient_id']
            sku_id = args['sku_id']
            quantity = args['quantity']

            current_user = kwargs.get("current_user")
            current_user_belong_bu = current_user.business_unit_employee
            current_user_belong_franchisee = current_user.franchisee_operator
            if current_user_belong_bu:
                unit_name = "BusinessUnit"
                unit_id = current_user_belong_bu.business_unit_id
            elif current_user_belong_franchisee:
                unit_name = "Franchisee"
                unit_id = current_user_belong_franchisee.franchisee_id
            else:
                raise Exception("当前用户没有归属店铺或者加盟商")

            addr_obj = CloudWineExpressOrders.query.get(recipient_id)
            sku_obj = db.session.query(SKU).with_for_update().filter(SKU.id.__eq__(sku_id),
                                                                     SKU.quantity.__ge__(eval(quantity))).first()

            if not addr_obj:
                raise Exception("无当前快递地址，请新增")

            if not sku_obj:
                raise Exception("无库存SKU")

            new_order = new_data_obj("CloudWineExpressOrders", **{"id": make_uuid(),
                                                                  "apply_id": current_user.id,
                                                                  "send_unit_type": unit_name,
                                                                  "send_unit_id": unit_id,
                                                                  "recipient_id": recipient_id,
                                                                  "apply_at": datetime.datetime.now(),
                                                                  })

            if not new_order:
                raise Exception("创建快递订单失败")

            return submit_return("创建快递订单成功", "创建快递订单失败")
        except Exception as e:
            return false_return(message=str(e))
