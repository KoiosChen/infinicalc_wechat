from flask_restplus import Resource, reqparse
from ..models import ShopOrders, Permission, ItemsOrders, Refund
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
from app.type_validation import checkout_sku_type
from ..wechat.pay import weixin_pay
import datetime

rebates_ns = default_api.namespace('rebates', path='/rebates', description='返佣API')

return_json = rebates_ns.model('ReturnRegister', return_dict)

