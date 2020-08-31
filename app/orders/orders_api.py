from flask_restplus import Resource, reqparse
from ..models import ShopOrders, Permission
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
from app.type_validation import checkout_sku_type
from ..wechat.pay import weixin_pay
import datetime

orders_ns = default_api.namespace('orders', path='/shop_orders', description='定单相关API')

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
cancel_parser.add_argument('cancel_reason', required=True, help='取消原因，让客户选择，不要填写')

order_page_parser = page_parser.copy()


@orders_ns.route('')
@orders_ns.expect(head_parser)
class ShopOrdersApi(Resource):
    @orders_ns.marshal_with(return_json)
    @orders_ns.doc(body=order_page_parser)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        args = order_page_parser.parse_args()
        return success_return(data=get_table_data(ShopOrders, args))


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
            return weixin_pay(kwargs['shop_order_id'], order.items_total_price, kwargs['current_user'].openid)
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
        try:
            args = cancel_parser.parse_args()
            order = ShopOrders.query.get(kwargs['shop_order_id'])
            if not order:
                raise Exception(f"{kwargs['shop_order_id']} 不存在")
            elif order.is_pay in (1, 2):
                raise Exception(f"当前支付状态不可退货")
            else:
                order.delete_at = datetime.datetime.now()
                order.cancel_reason = args.get('cancel_reason')
            return submit_return("取消成功", "取消失败")
        except Exception as e:
            return false_return(message=f"weixin pay failed: {str(e)}")



