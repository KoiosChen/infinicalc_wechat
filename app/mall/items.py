from flask import jsonify, request
from flask_restplus import Resource, fields, reqparse
from ..models import Users
from . import mall
from app.auth import auths
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
import datetime
from ..decorators import permission_required
from ..swagger import return_dict, head_parser
from .mall_api import mall_ns, return_json

items_parser = reqparse.RequestParser()
items_parser.add_argument('item_type', required=True, help='需要获取的商品类型recommended | all | assigned')
items_parser.add_argument('item_id', help='如果是assigned 类型，那么此变量不能为空')

items_set_parser = reqparse.RequestParser()
items_set_parser.add_argument('id', required=True, help='商品ID')
items_set_parser.add_argument('heading_name', required=True, help='商品上标题')
items_set_parser.add_argument('below_name', required=True, help='商品下标题')
items_set_parser.add_argument('type', required=True, help='商品类型')
items_set_parser.add_argument('service', help='商品附加服务')
items_set_parser.add_argument('quantity', required=True, help='商品数量')
items_set_parser.add_argument('price_original', required=True, help='商品原始价格')
items_set_parser.add_argument('discount_price', required=True, help='商品折扣, 0 ~ 1')
items_set_parser.add_argument('commodity_detail', required=True, help='商品描述')
items_set_parser.add_argument('product_pic', required=True, help='商品图片，list，每个元素是图片存储路径')
items_set_parser.add_argument('items_sub_name', help='商品子选项名称')
items_set_parser.add_argument('items_sub_thumbnail', help='商品子选项缩略图')
items_set_parser.add_argument('items_sub_price', help='商品子选项对应价格，若选中此子选项，那么下单价格为此选项价格')

