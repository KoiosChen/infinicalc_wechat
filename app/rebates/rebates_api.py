from flask_restplus import Resource, reqparse
from ..models import ShopOrders, Permission, ItemsOrders, Refund
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
from .calc_rebate import checkout_rebates_ratio
from app.type_validation import checkout_sku_type
from ..wechat.pay import weixin_pay
import datetime

rebates_ns = default_api.namespace('rebates', path='/rebates', description='返佣API')

return_json = rebates_ns.model('ReturnRegister', return_dict)

rebate_page_parser = page_parser.copy()
rebate_page_parser.add_argument('shop_order')


@rebates_ns.route('')
@rebates_ns.expect(head_parser)
class RebateApi(Resource):
    @rebates_ns.marshal_with(return_json)
    @rebates_ns.doc(body=rebate_page_parser)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """获取所有返佣"""
        args = rebate_page_parser.parse_args()
        args['search'] = {"delete_at": None}
        if not kwargs.get("current_user"):
            return false_return(f"user does not exist"), 403
        return checkout_rebates_ratio(kwargs['current_user'], args['shop_order'])

