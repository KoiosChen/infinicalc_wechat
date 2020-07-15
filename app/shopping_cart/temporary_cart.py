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
from .shopping_cart_api import shopping_cart_ns, return_json

temporary_cart_parser = reqparse.RequestParser()
temporary_cart_parser.add_argument('sku', required=True, type=checkout_sku_type,
                                   help="[{'id': {'required': True, 'type': str}, "
                                        " 'quantity': {'required': True, 'type': int},"
                                        " 'combo': {'type': str}}]"
                                        "combo中存放的是此sku对应的套餐促销活动中的利益表的ID，combo允许有多重组合套餐，所以在页面上呈现为多选一，选中的为对应的Benefits表的ID",
                                   location='json')
