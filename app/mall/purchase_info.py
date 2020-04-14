from flask_restplus import Resource, fields, reqparse
from ..models import Brands, SKU, sku_standardvalue, ImgUrl, PurchaseInfo
from . import mall
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
from ..public_method import table_fields, new_data_obj
from ..decorators import permission_required
from ..swagger import head_parser
from .mall_api import mall_ns, return_json
from datetime import datetime

delete_purchase_info = reqparse.RequestParser()
delete_purchase_info.add_argument("memo", required=True, help='作废原因')


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
                db.session.add(purchase_info)
                db.session.add(sku)
                return success_return(
                    f'作废进货单<{buy_id}>成功，'
                    f'SKU<{purchase_info.sku_id}>数量减少<{purchase_info.amount}>，'
                    f'现在为<{sku.quantity}>') if session_commit() else false_return(message=f"作废进货单失败"), 400
            else:
                return false_return(message=f"SKU <{sku.id}> 目前是上架状态，无法删除进货单，请先下架"), 400
        elif purchase_info and not purchase_info.status:
            return false_return(message=f"进货单 <{purchase_info.id}> 已经作废，不可操作"), 400
        else:
            return false_return(message=f"进货单不存在"), 400
