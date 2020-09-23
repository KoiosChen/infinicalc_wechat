from flask_restplus import Resource, reqparse
from ..models import ShopOrders, Permission, ItemsOrders, Refund, SKU
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id, order_cancel
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
from app.type_validation import checkout_sku_type
from ..wechat.pay import weixin_pay
import datetime

orders_ns = default_api.namespace('Orders', path='/shop_orders', description='定单相关API')

return_json = orders_ns.model('ReturnRegister', return_dict)

checkout_parser = reqparse.RequestParser()
checkout_parser.add_argument('sku', required=True, type=checkout_sku_type,
                             help="""传递数组，其中的元素为json：{'id': {'required': True, 'type': str},
                                    'quantity': {'required': True, 'type': int}}""",
                             location='json')
checkout_parser.add_argument('desc', help='促销活动描述')
checkout_parser.add_argument('group_id', required=True,
                             help='组ID， 0 为特殊组，特殊组和任何组不互斥。group_id 为-1表示是发优惠券，>=0的group，为活动')
checkout_parser.add_argument('priority', required=True, help='1-10, 10优先级最低，当有组互斥时，使用优先级最高的，0优先级最高')

cancel_parser = reqparse.RequestParser()
cancel_parser.add_argument('cancel_reason', help='取消原因，让客户选择，不要填写')

order_page_parser = page_parser.copy()

refund_parser = reqparse.RequestParser()
refund_parser.add_argument("refund_quantity", required=True, help="退货数量")
refund_parser.add_argument("collect_addr", required=True, help="取件地址")
refund_parser.add_argument("refund_reason", required=True,
                           choices=["商品损坏", "缺少件", "发错货", "商品与页面不相符", "商品降价", "不想要了", "质量问题", "其他"], help="退货原因")
refund_parser.add_argument("refund_desc", required=True, help='问题描述, 不超过200字符')
refund_parser.add_argument("images", type=list, location='json', help='前端限制最多传3张')

refund_auditor_parser = reqparse.RequestParser()
refund_auditor_parser.add_argument("audit_result", required=True, help="审核结果")
refund_auditor_parser.add_argument("express_no", required=True, help="快递号由后台人员填写")


@orders_ns.route('')
@orders_ns.expect(head_parser)
class ShopOrdersApi(Resource):
    @orders_ns.marshal_with(return_json)
    @orders_ns.doc(body=order_page_parser)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        args = order_page_parser.parse_args()
        args['search'] = {'customer_id': kwargs.get('current_user').id}
        data = get_table_data(ShopOrders, args, ['items_orders'])
        table = data['records']
        table.sort(key=lambda x: x['create_at'], reverse=True)
        return success_return(data=data)


@orders_ns.route('/<string:shop_order_id>/pay')
@orders_ns.expect(head_parser)
class ShopOrderPayApi(Resource):
    @orders_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def post(self, **kwargs):
        """提交支付"""
        try:
            order = ShopOrders.query.get(kwargs['shop_order_id'])
            if not order:
                raise Exception(f"{kwargs['shop_order_id']} 不存在")
            return weixin_pay(kwargs['shop_order_id'], order.items_total_price - order.score_used,
                              kwargs['current_user'].openid)
        except Exception as e:
            return false_return(message=f"weixin pay failed: {str(e)}")


@orders_ns.route('/<string:shop_order_id>/cancel')
@orders_ns.expect(head_parser)
class ShopOrderCancelApi(Resource):
    @orders_ns.marshal_with(return_json)
    @orders_ns.doc(body=cancel_parser)
    @permission_required(Permission.USER)
    def delete(self, **kwargs):
        """提交取消申请，如果订单是正在支付或者已支付，则不可取消，只能退货"""
        args = cancel_parser.parse_args()
        return order_cancel(args.get('cancel_reason'), kwargs['shop_order_id'])

# @orders_ns.route('/<string:item_order_id>/refund')
# @orders_ns.expect(head_parser)
# class ShopOrderRefundApi(Resource):
#     @orders_ns.marshal_with(return_json)
#     @orders_ns.doc(body=order_page_parser)
#     @permission_required([Permission.USER, "app.shop_orders.refund.get"])
#     def get(self, **kwargs):
#         """获取某个商品订单的退货申请"""
#         args = order_page_parser.parse_args()
#         args['search'] = {"item_order_id": kwargs['item_order_id'], "delete_at": None}
#         return success_return(get_table_data(Refund, args))
#
#     @orders_ns.marshal_with(return_json)
#     @orders_ns.doc(body=refund_parser)
#     @permission_required(Permission.USER)
#     def post(self, **kwargs):
#         """针对某个商品订单提交申请退货"""
#         try:
#             args = refund_parser.parse_args()
#             images = args.pop('images')
#
#             item_order = ItemsOrders.query.get(kwargs['item_order_id'])
#             if not item_order:
#                 raise Exception(f"{kwargs['item_order_id']}不存在")
#             if item_order.status != 1:
#                 raise Exception(f"当前{item_order.status}不可退货")
#             args['item_order_id'] = kwargs['item_order_id']
#             new_refund = new_data_obj("Refund", **args)
#
#             if new_refund and new_refund.get('status'):
#                 item_order.status = 3
#                 return submit_return("退货申请成功", "退货申请失败")
#             else:
#                 raise Exception("新建退货单失败")
#         except Exception as e:
#             return false_return(message=str(e))
