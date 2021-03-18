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
from app.scene_invitation.scene_invitation_api import generate_code

item_verification_ns = default_api.namespace('Items Verification', path='/items_verification', description='物品核销接口')

return_json = item_verification_ns.model('ReturnRegister', return_dict)

verify_quantity_parser = reqparse.RequestParser()
verify_quantity_parser.add_argument("sku_id", required=True, type=str, help='需要核销的sku id', location='args')
verify_quantity_parser.add_argument("quantity", required=True, type=str, help='核销数量', location='args')

verification_parser = reqparse.RequestParser()
verification_parser.add_argument("qrcode", required=True, type=str, help='get_verify_qrcode 返回的值')
verification_parser.add_argument('bu_id', required=True, type=str, help='用户核销入口所在的店铺ID')


@item_verification_ns.route('/pre_verification/<string:sku_id>')
@item_verification_ns.expect(head_parser)
class ItemPreVerification(Resource):
    @item_verification_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """获取对应SKU Item订单"""
        item_objs = ItemsOrders.query.filter(ItemsOrders.delete_at.__eq__(None),
                                             ItemsOrders.item_id.__eq__(kwargs['sku_id']),
                                             ItemsOrders.status.__eq__(1)).all()
        return success_return(data=sum(item_obj.left_verification_quantity for item_obj in item_objs))


@item_verification_ns.route('/get_verify_qrcode')
@item_verification_ns.expect(head_parser)
class ItemVerifyQRCode(Resource):
    @item_verification_ns.marshal_with(return_json)
    @item_verification_ns.doc(body=verify_quantity_parser)
    @permission_required(Permission.BU_WAITER)
    def get(self, **kwargs):
        """获取核销验证码"""
        args = verification_parser.parse_args()
        sku_id = args['sku_id']
        quantity = eval(args['quantity'])
        sum_item_quantity = sum(item_obj.item_quantity - item_obj.verified_quantity for item_obj in
                                db.session.query(ItemsOrders).with_for_update().filter(
                                    ItemsOrders.delete_at.__eq__(None),
                                    ItemsOrders.item_id.__eq__(sku_id),
                                    ItemsOrders.status.__eq__(1)).all())
        if sum_item_quantity < quantity:
            return false_return(message=f"取酒数量不可大于{sum_item_quantity}")
        else:
            qrcode = generate_code(16)
            args['present_quantity'] = sum_item_quantity
            redis_db.set(qrcode, args)
            redis_db.expire(qrcode, 120)
            return success_return(data=qrcode)


@item_verification_ns.route('/verify')
@item_verification_ns.expect(head_parser)
class ItemVerification(Resource):
    @item_verification_ns.marshal_with(return_json)
    @permission_required([Permission.BU_WAITER, "app.item_verification.ItemPreVerification.get"])
    def post(self, **kwargs):
        """核销订单中指定数量的sku, 取酒的入口在店铺中，所以可以传递店铺的id， 在店铺员工扫码核销的时候需要核对员工和店铺关系"""
        """核销环节需要检查时候需要返佣"""

        def __verify(to_verify_quantity):
            new_verify = new_data_obj("ItemVerification",
                                      **{"id": make_uuid(),
                                         "item_order_id": kwargs['item_order_id'],
                                         "verification_quantity": to_verify_quantity,
                                         "verification_customer_id": kwargs['current_user'].id,
                                         "bu_id": kwargs['current_user'].business_unit_employee.business_unit_id
                                         })
            item_order_obj.verified_quantity += to_verify_quantity

        args = verification_parser.parse_args()
        qrcode = args['qrcode']
        verify_quantity = qrcode['quantity']
        if not redis_db.exists(qrcode):
            return false_return(message='核销码无效')

        verify_info = redis_db.get(qrcode)
        redis_db.delete(qrcode)
        all_objs = db.session.query(ItemsOrders).with_for_update().filter(
            ItemsOrders.delete_at.__eq__(None),
            ItemsOrders.item_id.__eq__(verify_info['sku_id']),
            ItemsOrders.status.__eq__(1)).order_by(ItemsOrders.create_at.desc()).all()
        sum_item_quantity = sum(item_obj.item_quantity - item_obj.verified_quantity for item_obj in all_objs)
        if sum_item_quantity != verify_info['present_quantity']:
            return false_return(message='用户库存有变化，请重新生成核销码')

        current_user = kwargs['current_user']
        if not current_user.business_unit_employee or current_user.business_unit_employee.business_unit_id != kwargs[
            'bu_id']:
            return false_return(message=f'此员工无权核销'), 400

        for item_order_obj in all_objs:
            left_quantity = item_order_obj.item_quantity - item_order_obj.verified_quantity
            diff = left_quantity - verify_quantity

            if diff >= 0:
                # 表示核销完了
                __verify(verify_quantity)
                break
            elif diff < 0:
                # 说明核销不够，继续核销下一个订单
                verify_quantity = abs(diff)
                __verify(left_quantity)
        return submit_return("核销成功", "核销失败")