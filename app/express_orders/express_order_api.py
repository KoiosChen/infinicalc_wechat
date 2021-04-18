from flask_restplus import Resource, reqparse, cors
from flask import request
from . import express_orders
from ..models import Permission, CloudWineExpressAddress, CloudWineExpressOrders, SKU, make_uuid, FranchiseeInventory, \
    CustomerRoles
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, sort_by_order, submit_return
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id
from ..decorators import permission_required, allow_cross_domain
from ..swagger import return_dict, head_parser, page_parser
from sqlalchemy import or_
import datetime

express_ns = default_api.namespace('cloudwine_express', path='/cloudwine_express', description='客户发货申请及相关确认接口')

return_json = express_ns.model('ReturnRegister', return_dict)

express_order_page_parser = page_parser.copy()

new_express_order_parser = reqparse.RequestParser()
new_express_order_parser.add_argument("recipient", required=True, help='收件人')
new_express_order_parser.add_argument("recipient_phone", required=True, help='收件人电话')
new_express_order_parser.add_argument("recipient_addr", required=True, help='收件人地址')
new_express_order_parser.add_argument("sku_id", required=True, help='发货的sku id')
new_express_order_parser.add_argument("quantity", required=True, type=int, help='发货数量')
new_express_order_parser.add_argument("is_purchase", required=True, type=int, help='0 否，1 是')

update_express_order_parser = reqparse.RequestParser()
new_express_order_parser.add_argument("recipient", help='收件人')
new_express_order_parser.add_argument("recipient_phone", help='收件人电话')
new_express_order_parser.add_argument("recipient_addr", help='收件人地址')
update_express_order_parser.add_argument("sku_id", help='发货的SKU ID')
update_express_order_parser.add_argument("quantity", help='发货数量')
new_express_order_parser.add_argument("is_purchase", type=int, help='0 否，1 是')


@express_ns.route('')
@express_ns.expect(head_parser)
class ExpressOrderAPI(Resource):
    @express_ns.marshal_with(return_json)
    @express_ns.doc(body=express_order_page_parser)
    @permission_required([Permission.USER, "app.express_orders.express_order_api.ExpressOrderAPI.get"])
    def get(self, **kwargs):
        """查询所有快递订单列表，返回data中self_orders为自己发出的发货申请；confirm_orders只有调用接口的用户是加盟商老板才会有返回数据，
        返回的数据是这个加盟商老板需要确认的订单，按照创建时间倒序。return里的data格式为({"self_orders": self_orders, "confirm_orders": confirm_orders}。
        confirm_orders里的confirm_status=None，则为未确认订单，1为已确认，2为拒绝，加盟商老板的账户显示确认/拒绝按钮"""
        args = express_order_page_parser.parse_args()
        current_user = kwargs['current_user']
        self_args = args
        self_args['search']['customer_id'] = current_user.id
        self_orders = get_table_data(CloudWineExpressOrders, self_args, order_by="create_at")
        confirm_orders = dict()
        if current_user.franchisee_operator and current_user.franchisee_operator.role.name == "FRANCHISEE_MANAGER":
            confirm_args = args
            confirm_args['search']['franchisee_id'] = current_user.franchisee_operator.franchisee_id
            confirm_orders = get_table_data(CloudWineExpressOrders, confirm_args, order_by="create_at")
        return success_return({"self_orders": self_orders, "confirm_orders": confirm_orders}, "请求成功")

    @express_ns.marshal_with(return_json)
    @express_ns.doc(body=new_express_order_parser)
    @permission_required([Permission.USER, "app.express_orders.express_order_api.ExpressOrderAPI.post"])
    def post(self, **kwargs):
        """新建快递订单"""
        try:
            args = new_express_order_parser.parse_args()
            recipient = args['recipient']
            recipient_phone = args['recipient']
            recipient_addr = args['recipient_addr']
            sku_id = args['sku_id']
            quantity = args['quantity']
            is_purchase = args['is_purchase']
            franchisee_manager_role = CustomerRoles.query.filter_by(name='FRANCHISEE_MANAGER').first()
            current_user = kwargs.get("current_user")
            current_user_belong_bu = current_user.business_unit_employee
            current_user_belong_franchisee = current_user.franchisee_operator
            if current_user_belong_bu:
                unit_name = "BusinessUnit"
                unit_id = current_user_belong_bu.business_unit_id
                franchisee_id = current_user_belong_bu.business_unit.franchisee_id
            elif current_user_belong_franchisee:
                unit_name = "Franchisee"
                unit_id = current_user_belong_franchisee.franchisee_id
                franchisee_id = unit_id
            else:
                raise Exception("当前用户没有归属店铺或者加盟商")

            sku_obj = db.session.query(SKU).with_for_update().filter(SKU.id.__eq__(sku_id),
                                                                     SKU.quantity.__ge__(eval(quantity))).first()

            if not sku_obj:
                raise Exception("无库存SKU")

            franchisee_obj = db.session.query(FranchiseeInventory).with_for_update().filter(
                FranchiseeInventory.franchisee_id.__eq__(franchisee_id),
                FranchiseeInventory.sku_id.__eq__(sku_id),
                FranchiseeInventory.amount.__ge__(eval(quantity))).first()

            if not franchisee_obj:
                logger.warn("加盟商库存不足需要进货")

            new_order = new_data_obj("CloudWineExpressOrders", **{"id": make_uuid(),
                                                                  "apply_id": current_user.id,
                                                                  "send_unit_type": unit_name,
                                                                  "send_unit_id": unit_id,
                                                                  "recipient": recipient,
                                                                  "recipient_phone": recipient_phone,
                                                                  "recipient_addr": recipient_addr,
                                                                  "franchisee_id": franchisee_id,
                                                                  "is_purchase": is_purchase,
                                                                  "apply_at": datetime.datetime.now(),
                                                                  })

            if current_user.franchisee_operator.job_desc == franchisee_manager_role.id:
                # 如果当前用户是加盟商manager， 则直接完成确认步骤
                new_order['obj'].confirm_id = current_user.id
                new_order['obj'].confirm_at = datetime.datetime.now()

            if not new_order:
                raise Exception("创建快递订单失败")

            return submit_return("创建快递订单成功", "创建快递订单失败")
        except Exception as e:
            return false_return(message=str(e))


@express_ns.route('/<string:express_id>')
@express_ns.expect(head_parser)
class PerExpressOrderAPI(Resource):
    @express_ns.marshal_with(return_json)
    @express_ns.doc(body=update_express_order_parser)
    @permission_required([Permission.USER, "app.express_orders.per_express_order_api.ExpressOrderAPI.put"])
    def get(self, **kwargs):
        """获取指定订单详情"""
        return success_return(
            data=get_table_data_by_id(CloudWineExpressOrders, kwargs['express_id']))

    @express_ns.marshal_with(return_json)
    @express_ns.doc(body=update_express_order_parser)
    @permission_required([Permission.USER, "app.express_orders.per_express_order_api.ExpressOrderAPI.put"])
    def put(self, **kwargs):
        """修改快递订单，未发货前，申请人可修改此订单"""
        try:
            args = update_express_order_parser.parse_args()
            order_obj = db.session.query(CloudWineExpressOrders).with_for_update().filter(
                CloudWineExpressOrders.id.__eq__(kwargs['express_id'])).first()
            current_user = kwargs['current_user']

            apply_update_list = ("recipient", "recipient_phone", "recipient_addr", "sku_id", "quantity")
            confirm_update_list = ("confirm_status",)
            express_update_list = ("express_num",)

            if not order_obj:
                raise Exception("快递订单不存在")
            if order_obj.is_sent != 0:
                raise Exception('已发货，不可修改')

            inventory_obj = db.session.query(FranchiseeInventory).with_for_update().filter(
                FranchiseeInventory.franchisee_id.__eq__(order_obj.franchisee_id),
                FranchiseeInventory.sku_id.__eq__(order_obj.sku_id),
                FranchiseeInventory.amount.__ge__(order_obj.quantity)
            ).first()

            if not inventory_obj:
                raise Exception("加盟商无库存")

            # apply_update_flag = False

            for key, value in args.items():
                if hasattr(order_obj, key) and value:
                    if key in apply_update_list and current_user.id == order_obj.apply_id and order_obj.confirm_stauts == 0:
                        # apply_update_flag = True
                        setattr(order_obj, key, value)
                    elif key in confirm_update_list and current_user.franchisee_operator and current_user.franchisee_operator.franchisee_id == order_obj.franchisee_id:
                        if order_obj.confirm_id is None and order_obj.confirm_at is None and order_obj.confirm_stauts == 0:
                            if value == 1:
                                if not inventory_obj:
                                    raise Exception("库存不足，不可确认")
                                setattr(inventory_obj, "amount", inventory_obj.amount - order_obj.quantity)
                                if order_obj.is_purchase and order_obj.send_unit_type == 'BusinessUnit':
                                    new_purchase_order = new_data_obj("FranchiseePurchaseOrders",
                                                                      **{"franchisee_id": order_obj.franchisee_id,
                                                                         "sku_id": order_obj.sku_id,
                                                                         "amount": -order_obj.quantity,
                                                                         "status": 3,
                                                                         "purchase_from": None,
                                                                         "express_order": order_obj.id,
                                                                         "operate_at": datetime.datetime.now(),
                                                                         "operator": current_user.id})

                                    if not new_purchase_order or (
                                            new_purchase_order and not new_purchase_order['status']):
                                        raise Exception("创建加盟商出库单失败")

                                    new_bu_purchase_order = new_data_obj("BusinessPurchaseOrders",
                                                                         **{"bu_id": order_obj.send_unit_id,
                                                                            "amount": order_obj.quantity,
                                                                            "status": 3,
                                                                            "purchase_from": order_obj.franchisee_id,
                                                                            "original_order_id": new_purchase_order[
                                                                                'obj'].id})

                                    if not new_bu_purchase_order or (
                                            new_bu_purchase_order and not new_bu_purchase_order['status']):
                                        raise Exception("创建店铺入库单失败")

                                elif order_obj.is_purchase and order_obj.send_unit_type == 'Franchisee':
                                    # 如果是加盟商进货，需要扣减总库对应SKU的库存
                                    sku_obj = db.session.query(SKU).with_for_update().filter(SKU.id == order_obj.sku_id,
                                                                                             SKU.quantity.__ge__(
                                                                                                 order_obj.quantity)).first()
                                    if not sku_obj:
                                        return false_return(message=f"{order_obj.sku_id}不存在或者库存不足")

                                    sku_obj.quantity -= order_obj.quantity
                                    new_purchase_order = new_data_obj("PurchaseInfo", **{"sku_id": order_obj.sku_id,
                                                                                         "amount": -order_obj.quantity,
                                                                                         "operator": kwargs[
                                                                                             'current_user'].id,
                                                                                         "dispatch_status": 3,
                                                                                         "express_order": order_obj.id,
                                                                                         "operator_at": datetime.datetime.now(),
                                                                                         "express_to_id": order_obj.franchisee_id})
                                    if not new_purchase_order:
                                        return false_return(message="新建出库单失败")

                                    new_franchisee_purchase_order = new_data_obj("FranchiseePurchaseOrders",
                                                                                 **{"sku_id": order_obj.sku_id,
                                                                                    "amount": order_obj.quantity,
                                                                                    "status": 3,
                                                                                    "franchisee_id": order_obj.franchisee_id,
                                                                                    "original_order_id":
                                                                                        new_purchase_order[
                                                                                            'obj'].id
                                                                                    })

                                    if not new_franchisee_purchase_order:
                                        return false_return(message='加盟商新建入库单失败')

                            setattr(order_obj, "confirm_id", current_user.id)
                            setattr(order_obj, "confirm_at", datetime.datetime.now())
                            setattr(order_obj, "confirm_status", value)
                        else:
                            raise Exception("当前订单已确认，不可重复确认")
                    elif key in express_update_list and current_user.role == CustomerRoles.query.filter(
                            or_(CustomerRoles.name.__eq__("ADMINISTRATOR"),
                                CustomerRoles.name.__eq__("CUSTOMER_SERVICE"))).first():
                        if getattr(order_obj, key) is None:
                            setattr(order_obj, key, value)
                            setattr(order_obj, "express_company", "安能物流")
                            setattr(order_obj, "is_sent", 1)
                            setattr(order_obj, "send_at", datetime.datetime.now())

                            purchase_obj = getattr(order_obj, "purchase_order")
                            f_purchase_obj = getattr(order_obj, "franchisee_purchase_order")
                            if purchase_obj:
                                purchase_obj.dispatch_status = 1
                            if f_purchase_obj:
                                f_purchase_obj.status = 1
                        else:
                            raise Exception("当前订单已发货，不可重复发货")
                    else:
                        raise Exception("当前用户不可修改此订单")
                else:
                    logger.error(f"{key} attribute not exist")

            # if apply_update_flag:
            #     # 需要重新确认
            #     setattr(order_obj, "confirm_id", None)
            #     setattr(order_obj, "confirm_at", None)
            #     setattr(order_obj, "confirm_status", None)
            return submit_return("修改成功", "修改失败")
        except Exception as e:
            return false_return(message=str(e))

    @express_ns.marshal_with(return_json)
    @permission_required([Permission.USER, "app.express_orders.per_express_order_api.ExpressOrderAPI.delete"])
    def delete(self, **kwargs):
        """提交申请后，未审核、未发货则可删除"""
        try:

            order_obj = CloudWineExpressOrders.query.get(kwargs['express_id'])

            if not order_obj:
                raise Exception("快递订单不存在")

            if order_obj.confirm_stauts != 0:
                raise Exception("订单已确认，不可删除")

            if order_obj.is_sent != 0:
                raise Exception('已发货，不可删除')

            if kwargs['current_user'].id != order_obj.apply_id:
                raise Exception('当前用户无权删除此订单')

            db.session.delete(order_obj)
            return submit_return("删除成功", "删除失败")

        except Exception as e:
            return false_return(message=str(e))
