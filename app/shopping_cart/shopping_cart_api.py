from flask_restplus import Resource, reqparse
from ..models import SKU, ShopOrders, Promotions
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, nesteddict
from ..decorators import permission_required
from ..swagger import return_dict, head_parser
from app.type_validation import checkout_sku_type
from collections import defaultdict
import datetime
from decimal import Decimal

shopping_cart_ns = default_api.namespace('购物车', path='/shopping_cart', description='购物车API')

return_json = shopping_cart_ns.model('ReturnRegister', return_dict)

shopping_cart_parser = reqparse.RequestParser()
shopping_cart_parser.add_argument('sku', required=True, type=checkout_sku_type,
                                  help="[{'id': {'required': True, 'type': str}, "
                                       " 'quantity': {'required': True, 'type': int},"
                                       " 'combo': {'benefits_id': str, 'gifts':[gift_id]}}]"
                                       "combo中存放的是此sku对应的套餐促销活动中的利益表的ID，combo允许有多重组合套餐，所以在页面上呈现为多选一，选中的为对应的Benefits表的ID",
                                  location='json')


@shopping_cart_ns.route('')
@shopping_cart_ns.expect(head_parser)
class ProceedCheckOut(Resource):
    @shopping_cart_ns.doc(body=shopping_cart_parser)
    @shopping_cart_ns.marshal_with(return_json)
    @permission_required("frontstage.app.shopping_cart.check_out")
    def post(self, **kwargs):
        """显示购物车"""
        args = shopping_cart_parser.parse_args().get("sku")
