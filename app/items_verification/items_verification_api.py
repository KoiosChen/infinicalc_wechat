from flask_restplus import Resource, reqparse
from ..models import ShopOrders, Permission, ItemsOrders, Refund, make_uuid
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
from app.type_validation import checkout_sku_type
from ..wechat.pay import weixin_pay
import datetime

item_verification_ns = default_api.namespace('Items Verification', path='/items_verification', description='物品核销接口')

return_json = item_verification_ns.model('ReturnRegister', return_dict)

verification_parser = reqparse.RequestParser()
verification_parser.add_argument("original_quantity", required=True, type=int, help='pre_verification中返回的数值')
verification_parser.add_argument("verification_quantity", required=True, type=int, help='核销的数量，小于等于original_quantity')


@item_verification_ns.route('/<string:item_order_id>/pre_verification')
@item_verification_ns.expect(head_parser)
class ItemPreVerification(Resource):
    @item_verification_ns.marshal_with(return_json)
    @permission_required([Permission.BU_WAITER, "app.item_verification.ItemPreVerification.get"])
    def get(self, **kwargs):
        """获取可核销数量"""
        item_order_obj = db.session.query(ItemsOrders).with_for_update().filter(
            ItemsOrders.id.__eq__(kwargs['item_order_id'])).first()
        # 此处预生成一个核销订单号，写在redis里，1分钟有效用于生成一次性核销二维码
        new_id = make_uuid()
        redis_db.set(kwargs['item_order_id'], new_id)
        redis_db.expire(kwargs['item_order_id'], 60)
        return success_return(data={"verification_id": new_id,
                                    "left_verification_quantity": item_order_obj.left_verification_quantity})


@item_verification_ns.route('/<string:item_order_id>/business_unit/<string:bu_id>/verification')
@item_verification_ns.expect(head_parser)
class ItemVerification(Resource):
    @item_verification_ns.marshal_with(return_json)
    @permission_required([Permission.BU_WAITER, "app.item_verification.ItemPreVerification.get"])
    def post(self, **kwargs):
        """核销订单中指定数量的sku, 取酒的入口在店铺中，所以可以传递店铺的id， 在店铺员工扫码核销的时候需要核对员工和店铺关系"""
        """核销环节需要检查时候需要返佣"""
        args = verification_parser.parse_args()
        current_user = kwargs['current_user']
        if not current_user.business_unit_employee or current_user.business_unit_employee.business_unit_id != kwargs['bu_id']:
            return false_return(message=f'此员工无权核销'), 400
        if not redis_db.exists(kwargs['item_order_id']):
            return false_return(message="二维码一分钟内有效，已过期请重新生成"), 400
        else:
            new_id = redis_db.get(args['item_order_id'])
            redis_db.delete(args['item_order_id'])

        item_order_obj = db.session.query(ItemsOrders).with_for_update().filter(
            ItemsOrders.id.__eq__(kwargs['item_order_id']),
            ItemsOrders.left_verification_quantity.__eq__(args['original_quantity']),
            ItemsOrders.left_verification_quantity.__ge__(args['verification_quantity'])).first()

        if not item_order_obj:
            return false_return(message="无可核销订单")
        else:
            left_verification_quantity = item_order_obj.left_verification_quantity - args['verification_quantity']
            new_verify = new_data_obj("ItemVerification",
                                      **{"id": new_id,
                                         "item_order_id": kwargs['item_order_id'],
                                         "left_verification_quantity": left_verification_quantity,
                                         "verification_customer_id": kwargs['current_user'].id,
                                         "bu_id": kwargs['current_user'].business_unit_employee.business_unit_id
                                         })
            item_order_obj.left_verification_quantity = left_verification_quantity
            if not new_verify:
                return false_return(message="verify item failed")
            else:
                return submit_return("success", "fail")
