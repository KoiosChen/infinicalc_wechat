from flask_restplus import Resource, reqparse
from ..models import SKU, PurchaseInfo, Permission
from . import mall
from .. import db, logger
from ..public_method import new_data_obj
from ..common import false_return, submit_return
from ..decorators import permission_required
from ..swagger import head_parser
from .mall_api import mall_ns, return_json
from datetime import datetime

delete_purchase_info = reqparse.RequestParser()
delete_purchase_info.add_argument("memo", required=True, help='作废原因')

dispatch_parser = reqparse.RequestParser()
dispatch_parser.add_argument("sku_id", required=True, help='要发货的sku id')
dispatch_parser.add_argument("amount", required=True, type=int, help='发货数量')


@mall_ns.route('/purchase_info/<string:buy_id>')
@mall_ns.param('buy_id', '进货单ID')
@mall_ns.expect(head_parser)
class PerPurchase(Resource):
    @mall_ns.doc(body=delete_purchase_info)
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.purchase_info.delete_purchase")
    def delete(self, **kwargs):
        """作废进货单"""
        args = delete_purchase_info.parse_args()
        buy_id = kwargs['buy_id']
        purchase_info = PurchaseInfo.query.get(buy_id)
        if purchase_info and purchase_info.status == 1:
            purchase_info.memo = args['memo']
            purchase_info.status = 0
            purchase_info.operator = kwargs['info']['user'].id
            purchase_info.update_at = datetime.now()
            sku = SKU.query.get(purchase_info.sku_id)
            if not sku.status:
                sku.quantity -= purchase_info.amount
                db.session.flush()
                db.session.add(purchase_info)
                db.session.add(sku)
                return submit_return(
                    f'作废进货单<{buy_id}>成功，SKU<{purchase_info.sku_id}>数量减少<{purchase_info.amount}>，现在为<{sku.quantity}>',
                    f"作废进货单失败")
            else:
                return false_return(message=f"SKU <{sku.id}> 目前是上架状态，无法删除进货单，请先下架"), 400
        elif purchase_info and not purchase_info.status:
            return false_return(message=f"进货单 <{purchase_info.id}> 已经作废，不可操作"), 400
        else:
            return false_return(message=f"进货单不存在"), 400


@mall_ns.route('/purchase_info/dispatch/franchisee/<string:franchisee_id>')
@mall_ns.param('franchisee_id', '加盟商ID')
@mall_ns.expect(head_parser)
class DispatchFranchisee(Resource):
    @mall_ns.doc(body=dispatch_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required([Permission.ADMINISTRATOR, "app.mall.purchase_info.DispatchFranchisee.post"])
    def post(self, **kwargs):
        """发货到加盟商"""
        args = dispatch_parser.parse_args()
        amount = args['amount'] if isinstance(args['amount'], int) else eval(args['amount'])
        sku_id = args['sku_id']
        franchisee_id = kwargs['franchisee_id']
        sku_obj = db.session.query(SKU).with_for_update().filter(SKU.id == sku_id,
                                                                 SKU.quantity.__ge__(amount)).first()
        if not sku_obj:
            return false_return(message=f"{sku_id}不存在或者库存不足")

        sku_obj.quantity -= amount
        new_purchase_order = new_data_obj("PurchaseInfo", **{"sku_id": sku_id,
                                                             "amount": -amount,
                                                             "operator": kwargs['current_user'].id,
                                                             "operator_at": datetime.now(),
                                                             "express_to_id": franchisee_id})
        if not new_purchase_order:
            return false_return(message="新建出库单失败")

        new_franchisee_purchase_order = new_data_obj("FranchiseePurchaseOrders",
                                                     **{"sku_id": sku_id,
                                                        "amount": amount,
                                                        "franchisee_id": franchisee_id,
                                                        "original_order_id": new_purchase_order['obj'].id
                                                        })
        if not new_franchisee_purchase_order:
            return false_return(message='加盟商新建入库单失败')

        return submit_return("出库成功，待加盟商确认后入库", "出库失败")
