from flask_restplus import Resource, reqparse
from ..models import ShopOrders, Permission, ItemsOrders, Refund, ObjStorage, Customers
from .. import default_api, logger
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import new_data_obj, get_table_data, order_cancel, \
    order_payed_couponscards
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
from app.type_validation import checkout_sku_type
from ..wechat.pay import weixin_pay
from ..wechat.order_check import weixin_orderquery
import datetime
import traceback
from sqlalchemy import and_

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

order_ship_parser = reqparse.RequestParser()
order_ship_parser.add_argument('express_company', required=True, help='快递公司, 必填')
order_ship_parser.add_argument('express_number', required=True, help='快递单号, 必填')

order_receive_parser = reqparse.RequestParser()
order_receive_parser.add_argument('is_receipt', required=True, help='1, 已发货未签收，2，已发货已签收', location='json')

cancel_parser = reqparse.RequestParser()
cancel_parser.add_argument('cancel_reason', help='取消原因，让客户选择，不要填写')

order_page_parser = page_parser.copy()
order_page_parser.add_argument("is_pay", type=int, help='查询支付状态', location='args')
order_page_parser.add_argument("id", help='订单ID', location='args')
order_page_parser.add_argument("agent_nickname", help='代理商微信昵称， customers.username', location='args')
order_page_parser.add_argument("is_ship", help="0：未发货，1：已发货", location='args')
order_page_parser.add_argument("is_receipt", help='0：未发货 1：已发货未签收 2：已发货已签收', location='args')
order_page_parser.add_argument("status", help="1：正常 2：禁用 0：订单取消(delete_at 写入时间)", location='args')
order_page_parser.add_argument("interest_id", location='args', help="代理商ID")

refund_parser = reqparse.RequestParser()
refund_parser.add_argument("refund_quantity", required=True, help="退货数量")
refund_parser.add_argument("collect_addr", required=True, help="取件地址")
refund_parser.add_argument("refund_reason", required=True,
                           choices=["商品损坏", "缺少件", "发错货", "商品与页面不相符", "商品降价", "不想要了", "质量问题", "其他"], help="退货原因")
refund_parser.add_argument("refund_desc", required=True, help='问题描述, 不超过200字符')
refund_parser.add_argument("images", type=list, location='json', help='退货商品图片，前端限制最多传3张')

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
        """获取当前登录用户账户下所有订单，按照创建时间倒序"""
        args = order_page_parser.parse_args()
        args['search'] = {'customer_id': kwargs.get('current_user').id}
        data = get_table_data(ShopOrders, args, ['items_orders', 'real_payed_cash_fee'])
        table = data['records']
        table.sort(key=lambda x: x['create_at'], reverse=True)
        return success_return(data=data)


@orders_ns.route('/all')
@orders_ns.expect(head_parser)
class AllShopOrdersApi(Resource):
    @orders_ns.marshal_with(return_json)
    @orders_ns.doc(body=order_page_parser)
    @permission_required("app.orders.all_shop_orders")
    def get(self, **kwargs):
        """后台管理员获取所有订单，按照创建时间倒序， 返回值中customer_info是下订单用户的用户信息"""
        args = order_page_parser.parse_args()
        args['search'] = dict()
        agent_search = list()
        advance_search = list()
        if args.get("is_pay"):
            args['search']['is_pay'] = args['is_pay']
        if args.get("id"):
            args['search']['id'] = args['id']
        if args.get("is_ship"):
            args['search']['is_ship'] = args['is_ship']
        if args.get('is_receipt'):
            args['search']['is_receipt'] = args['is_receipt']
        if args.get('status'):
            args['search']['status'] = args['status']
        if args.get('interest_id'):
            agent_search.append(Customers.id.__eq__(args['interest_id']))
        if args.get('agent_nickname'):
            agent_search.append(Customers.username.contains(args['agent_nickname']))

        if agent_search:
            advance_search.append({"key": "customer_id",
                                   "operator": "in_",
                                   "value": [c.id for c in Customers.query.filter(and_(*agent_search)).all()]})
        data = get_table_data(ShopOrders, args,
                              appends=['customer_info', 'real_payed_cash_fee', 'items_orders'],
                              removes=['customers_id'],
                              order_by='create_at',
                              advance_search=advance_search)
        return success_return(data=data)


@orders_ns.route('/<string:shop_order_id>/ship')
@orders_ns.expect(head_parser)
class ShopOrderShipApi(Resource):
    @orders_ns.marshal_with(return_json)
    @orders_ns.doc(body=order_ship_parser)
    @permission_required("app.orders.order_api.shop_order_ship")
    def put(self, **kwargs):
        """修改订单发货"""
        try:
            args = order_ship_parser.parse_args()
            order_obj = ShopOrders.query.get(kwargs['shop_order_id'])
            if not order_obj:
                raise Exception(f"<{kwargs['shop_order_id']}>不存在")

            if not args.get('express_company') or not args.get('express_number'):
                raise Exception("快递信息不能为空值")

            order_obj.express_company = args.get('express_company')
            order_obj.express_number = args.get('express_number')
            order_obj.is_ship = 1
            order_obj.ship_time = datetime.datetime.now()
            order_obj.is_receipt = 1
            if session_commit().get('code') != 'success':
                raise Exception("数据提交失败")
            else:
                return success_return(message="发货成功")
        except Exception as e:
            traceback.print_exc()
            return false_return(message=str(e))


@orders_ns.route('/<string:shop_order_id>/receive')
@orders_ns.expect(head_parser)
class ShopOrderReceiveApi(Resource):
    @orders_ns.marshal_with(return_json)
    @orders_ns.doc(body=order_receive_parser)
    @permission_required("app.orders.order_api.shop_order_revceive")
    def put(self, **kwargs):
        """修改订单收货"""
        try:
            args = order_receive_parser.parse_args()
            order_obj = ShopOrders.query.get(kwargs['shop_order_id'])
            if not order_obj:
                raise Exception(f"<{kwargs['shop_order_id']}>不存在")

            if not args.get('is_receipt'):
                raise Exception("收货状态不能为空值")

            order_obj.is_receipt = 2
            order_obj.receive_time = datetime.datetime.now()
            if session_commit().get('code') != 'success':
                raise Exception("数据提交失败")
            else:
                return success_return(message="收货状态修改成功")
        except Exception as e:
            traceback.print_exc()
            return false_return(message=str(e))


@orders_ns.route('/<string:shop_order_id>/pay')
@orders_ns.expect(head_parser)
class ShopOrderPayApi(Resource):
    @orders_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def post(self, **kwargs):
        """若在购物车提交支付失败，或者支付中取消，可在订单管理中调用此接口进行支付"""
        try:
            order = ShopOrders.query.get(kwargs['shop_order_id'])
            coupon_reduce, card_reduce = order_payed_couponscards(order)

            return weixin_pay(kwargs['shop_order_id'],
                              order.items_total_price - order.score_used - coupon_reduce - card_reduce,
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


@orders_ns.route('/<string:item_order_id>/refund')
@orders_ns.expect(head_parser)
class ItemOrderRefundApi(Resource):
    @orders_ns.marshal_with(return_json)
    @orders_ns.doc(body=order_page_parser)
    @permission_required([Permission.USER, "app.shop_orders.refund.get"])
    def get(self, **kwargs):
        """获取某个商品订单的退货申请"""
        args = order_page_parser.parse_args()
        args['search'] = {"item_order_id": kwargs['item_order_id'], "delete_at": None}
        return success_return(get_table_data(Refund, args))

    @orders_ns.marshal_with(return_json)
    @orders_ns.doc(body=refund_parser)
    @permission_required(Permission.USER)
    def post(self, **kwargs):
        """针对某个商品订单提交申请退货"""
        try:
            args = refund_parser.parse_args()
            images = args.pop('images')

            item_order = ItemsOrders.query.get(kwargs['item_order_id'])
            if not item_order:
                raise Exception(f"{kwargs['item_order_id']}不存在")
            if item_order.status != 1:
                raise Exception(f"当前{item_order.status}不可退货")
            args['item_order_id'] = kwargs['item_order_id']
            new_refund = new_data_obj("Refund", **args)

            if new_refund and new_refund.get('status'):
                item_order.status = 3
                if images:
                    for image in images:
                        new_refund.images.append(ObjStorage.query.get(image))
                return submit_return("退货申请成功", "退货申请失败")
            else:
                raise Exception("新建退货单失败")
        except Exception as e:
            return false_return(message=str(e))


@orders_ns.route('/wechat_pay/<string:order_id>')
@orders_ns.expect(head_parser)
@orders_ns.param("order_id", "订单编号")
class OrderQuery(Resource):
    @orders_ns.marshal_with(return_json)
    @permission_required([Permission.USER, "app.order.order_query"])
    def get(self, **kwargs):
        """
        调用微信order_query接口，手工获取订单状态
        """
        logger.debug(kwargs['order_id'])
        return success_return(weixin_orderquery(kwargs['order_id']))
