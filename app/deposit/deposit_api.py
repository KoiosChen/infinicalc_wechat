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

deposit_ns = default_api.namespace('Deposit', path='/deposit', description='存酒接口')

return_json = deposit_ns.model('ReturnRegister', return_dict)

deposit_parser = reqparse.RequestParser()
deposit_parser.add_argument("sku_id", required=True, type=str, help='需要寄存酒的SKU')

deposit_parser.add_argument('objects', type=list, help='寄存酒的照片', location='json')

deposit_parser.add_argument("verification_quantity", required=True, type=int, help='核销的数量，小于等于original_quantity')
