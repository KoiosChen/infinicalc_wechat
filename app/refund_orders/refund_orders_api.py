from flask_restplus import Resource, reqparse
from ..models import ShopOrders, Permission, ItemsOrders, Refund
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
from app.type_validation import checkout_sku_type
from ..wechat.refund import weixin_refund
import datetime

refund_ns = default_api.namespace('Refund', path='/refund', description='退货定单相关API')

refund_page_parser = page_parser.copy()

return_json = refund_ns.model('ReturnRegister', return_dict)

refund_auditor_parser = reqparse.RequestParser()
refund_auditor_parser.add_argument("status", required=True, help='审核结果，1 通过 2 拒绝')
refund_auditor_parser.add_argument("audit_result", required=True, help="审核结果")
refund_auditor_parser.add_argument("express_no", required=True, help="快递号由后台人员填写")


@refund_ns.route('')
@refund_ns.expect(head_parser)
class RefundOrdersApi(Resource):
    @refund_ns.marshal_with(return_json)
    @refund_ns.doc(body=refund_page_parser)
    @permission_required("app.refund.get_all")
    def get(self, **kwargs):
        """获取所有"""
        args = refund_page_parser.parse_args()
        args['search'] = {"delete_at": None}
        return success_return(data=get_table_data(Refund, args))


@refund_ns.route('/<string:refund_id>')
@refund_ns.expect(head_parser)
class RefundByID(Resource):
    @refund_ns.marshal_with(return_json)
    @permission_required([Permission.USER, "app.refund.get_by_id"])
    def get(self, **kwargs):
        """获取某个退货申请详情"""
        return success_return(get_table_data_by_id(Refund, kwargs['refund_id']))

    @refund_ns.marshal_with(return_json)
    @refund_ns.doc(body=refund_auditor_parser)
    @permission_required(Permission.USER)
    def put(self, **kwargs):
        """审核某个退货订单"""
        try:
            args = refund_auditor_parser.parse_args()
            refund_order = Refund.query.filter(Refund.id == kwargs['refund_id'], Refund.status == 1,
                                               Refund.delete_at == None).first()
            if not refund_order:
                raise Exception(f"退货订单{kwargs['refund_id']}不存在, 或者状态不可退货")

            item_order = ItemsOrders.query.filter(ItemsOrders.id == refund_order.item_order_id,
                                                  ItemsOrders.status == 3, ItemsOrders.delete_at == None).first()
            if not item_order:
                raise Exception(f"商品订单{refund_order.item_order_id}不存在, 或者状态不可退货")

            refund_order.status = args['status']
            refund_order.audit_result = args['audit_result']
            refund_order.express_no = args['express_no']
            if args['status'] == '1':
                item_order.status = 4
            elif args['status'] == '2':
                item_order.status = 1
            db.session.add(item_order)
            return submit_return("审核修改成功", "审核修改失败")
        except Exception as e:
            return false_return(message=str(e)), 400

    @refund_ns.marshal_with(return_json)
    @permission_required("app.refund.post_weixin_refund_query")
    def post(self, **kwargs):
        """请求微信退款接口"""
        return success_return(weixin_refund(kwargs['refund_id']))
