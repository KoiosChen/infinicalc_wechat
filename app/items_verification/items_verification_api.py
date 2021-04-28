from flask_restplus import Resource, reqparse
from ..models import Permission, ItemsOrders, make_uuid, ItemVerification, BusinessUnitInventory
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, submit_return
from ..public_method import new_data_obj, get_table_data
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
import json
from app.scene_invitation.scene_invitation_api import generate_code
from app.rebate_calc import *
import datetime

item_verification_ns = default_api.namespace('items verification', path='/items_verification', description='物品核销接口')

return_json = item_verification_ns.model('ReturnRegister', return_dict)

all_verification_orders = reqparse.RequestParser()
all_verification_orders.add_argument("item_order_id", required=False, help='根据商品订单好来查询其所有核销订单', location='args')
all_verification_orders.add_argument("bu_id", required=False, help='店铺ID，查询该用户在指定店铺下的所有核销订单', location='args')

verify_quantity_parser = reqparse.RequestParser()
verify_quantity_parser.add_argument("sku_id", required=True, type=str, help='需要核销的sku id', location='args')
verify_quantity_parser.add_argument("quantity", required=True, help='核销数量', location='args')
verify_quantity_parser.add_argument("bu_id", required=True, type=str, help='进入取酒的这个店铺的id', location='args')

verification_parser = reqparse.RequestParser()
verification_parser.add_argument("qrcode", required=True, type=str, help='get_verify_qrcode 返回的值')
verification_parser.add_argument('bu_id', required=True, type=str, help='用户核销入口所在的店铺ID')


@item_verification_ns.route('')
@item_verification_ns.expect(head_parser)
class ItemVerificationOrders(Resource):
    @item_verification_ns.marshal_with(return_json)
    @item_verification_ns.doc(body=all_verification_orders)
    @permission_required(Permission.BU_WAITER)
    def get(self, **kwargs):
        """店铺员工获取自己核销的所有核销单，可通过状态查询"""
        current_user = kwargs['current_user']
        args = all_verification_orders.parse_args()
        args['search'] = dict()
        for k, v in args.items():
            if v:
                args['search'][k] = v
        args['search']['delete_at'] = None
        args['search']['verification_customer_id'] = current_user.id
        return success_return(data=get_table_data(ItemVerification, args,
                                                  appends=['items_orders', 'bu'],
                                                  removes=['item_order_id', 'bu_id']))


@item_verification_ns.route('/self_item_verification_orders')
@item_verification_ns.expect(head_parser)
class SelfItemVerificationOrders(Resource):
    @item_verification_ns.marshal_with(return_json)
    @item_verification_ns.doc(body=all_verification_orders)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """获取用自己的核销记录"""
        current_user = kwargs['current_user']
        args = all_verification_orders.parse_args()
        args['search'] = dict()
        for k, v in args.items():
            if v:
                args['search'][k] = v
        args['search']['delete_at'] = None
        args['search']['customer_id'] = current_user.id
        return success_return(data=get_table_data(ItemVerification, args,
                                                  appends=['items_orders', 'bu'],
                                                  removes=['item_order_id', 'bu_id']))


@item_verification_ns.route('/pre_verification/<string:sku_id>')
@item_verification_ns.expect(head_parser)
class ItemPreVerification(Resource):
    @item_verification_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """获取对应SKU Item订单"""
        item_objs = ItemsOrders.query.filter(ItemsOrders.delete_at.__eq__(None),
                                             ItemsOrders.item_id.__eq__(kwargs['sku_id']),
                                             ItemsOrders.status.__eq__(1),
                                             ItemsOrders.customer_id.__eq__(kwargs['current_user'].id)).all()
        return success_return(data=sum(item_obj.item_quantity - item_obj.verified_quantity for item_obj in item_objs))


@item_verification_ns.route('/get_verify_qrcode')
@item_verification_ns.expect(head_parser)
class ItemVerifyQRCode(Resource):
    @item_verification_ns.marshal_with(return_json)
    @item_verification_ns.doc(body=verify_quantity_parser)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """获取核销验证码"""
        args = verify_quantity_parser.parse_args()
        current_user = kwargs['current_user']

        sku_id = args['sku_id']
        quantity = eval(args['quantity'])

        bu_inventory_obj = BusinessUnitInventory.query.filter(BusinessUnitInventory.bu_id.__eq__(args['bu_id']),
                                                              BusinessUnitInventory.sku_id.__eq__(sku_id)).first()

        if bu_inventory_obj.amount < quantity:
            return false_return(message='店铺库存不足'), 400

        all_items_objs = db.session.query(ItemsOrders).with_for_update().filter(
                                    ItemsOrders.delete_at.__eq__(None),
                                    ItemsOrders.item_id.__eq__(sku_id),
                                    ItemsOrders.status.__eq__(1),
                                    ItemsOrders.customer_id.__eq__(current_user.id)).all()

        sum_item_quantity = sum(item_obj.item_quantity - item_obj.verified_quantity for item_obj in all_items_objs)
        if sum_item_quantity < quantity:
            return false_return(message=f"取酒数量不可大于{sum_item_quantity}")
        else:
            qrcode = generate_code(16)
            args['present_quantity'] = sum_item_quantity
            redis_db.set(qrcode,
                         json.dumps({"sku_id": sku_id, "customer_id": current_user.id, "quantity": quantity,
                                     "present_quantity": sum_item_quantity}))
            redis_db.expire(qrcode, 120)
            return success_return(data=qrcode)


@item_verification_ns.route('/verify')
@item_verification_ns.expect(head_parser)
class ItemVerificationAPI(Resource):
    @item_verification_ns.marshal_with(return_json)
    @item_verification_ns.doc(body=verification_parser)
    @permission_required([Permission.BU_WAITER, "app.item_verification.ItemPreVerification.get"])
    def post(self, **kwargs):
        """核销订单中指定数量的sku, 取酒的入口在店铺中，所以可以传递店铺的id， 在店铺员工扫码核销的时候需要核对员工和店铺关系"""
        """核销环节需要检查时候需要返佣"""

        def __verify(to_verify_quantity, item_order_obj):
            new_verify = new_data_obj("ItemVerification",
                                      **{"id": make_uuid(),
                                         "item_order_id": item_order_obj.id,
                                         "verification_quantity": to_verify_quantity,
                                         "verification_customer_id": kwargs['current_user'].id,
                                         "bu_id": args['bu_id']
                                         })

            new_sell_order = new_data_obj("BusinessPurchaseOrders",
                                          **{"amount": -to_verify_quantity,
                                             "sell_to": item_order_obj.shop_orders.customer_id,
                                             "status": 1,
                                             "sku_id": item_order_obj.item_id,
                                             "bu_id": args['bu_id'],
                                             "operator": kwargs['current_user'].id,
                                             "operate_at": datetime.datetime.now()})
            bu_inventory_obj = BusinessUnitInventory.query.filter(BusinessUnitInventory.bu_id.__eq__(args['bu_id']),
                                                                  BusinessUnitInventory.sku_id.__eq__(
                                                                      item_order_obj.item_id)).first()
            bu_inventory_obj.amount -= to_verify_quantity
            item_order_obj.verified_quantity += to_verify_quantity
            return new_verify['obj'].id

        args = verification_parser.parse_args()
        qrcode = args['qrcode']
        if not redis_db.exists(qrcode):
            return false_return(message='核销码无效')

        verify_info = json.loads(redis_db.get(qrcode))
        verify_quantity = verify_info['quantity']
        redis_db.delete(qrcode)
        all_objs = db.session.query(ItemsOrders).with_for_update().filter(
            ItemsOrders.delete_at.__eq__(None),
            ItemsOrders.item_id.__eq__(verify_info['sku_id']),
            ItemsOrders.status.__eq__(1),
            ItemsOrders.customer_id.__eq__(verify_info['customer_id'])).order_by(ItemsOrders.create_at).all()
        sum_item_quantity = sum(item_obj.item_quantity - item_obj.verified_quantity for item_obj in all_objs)
        if sum_item_quantity != verify_info['present_quantity']:
            return false_return(message='用户库存有变化，请重新生成核销码')

        current_user = kwargs['current_user']
        if not current_user.business_unit_employee or current_user.business_unit_employee.business_unit_id != args[
            'bu_id']:
            return false_return(message=f'此员工无权核销'), 400

        bu_inventory_obj = BusinessUnitInventory.query.filter(BusinessUnitInventory.bu_id.__eq__(args['bu_id']),
                                                              BusinessUnitInventory.sku_id.__eq__(
                                                                  verify_info['sku_id'])).first()

        if bu_inventory_obj.amount < verify_quantity:
            return false_return(message='店铺库存不足'), 400

        for item_order_obj in all_objs:
            left_quantity = item_order_obj.item_quantity - item_order_obj.verified_quantity
            diff = left_quantity - verify_quantity

            if diff >= 0:
                # 表示核销完了
                vid = __verify(verify_quantity, item_order_obj)
                rebate_result = pickup_rebate(vid, current_user.business_unit_employee.id,
                                              item_order_obj.customer_id)
                logger.error(rebate_result)
                break
            elif diff < 0:
                # 说明核销不够，继续核销下一个订单
                verify_quantity = abs(diff)
                vid = __verify(left_quantity, item_order_obj)
                rebate_result = pickup_rebate(vid, current_user.business_unit_employee.id,
                                              item_order_obj.shop_orders.customer_id)
                logger.error(rebate_result)

        return submit_return("核销成功", "核销失败")
