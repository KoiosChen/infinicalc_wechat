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

coupon_parser = reqparse.RequestParser()
coupon_parser.add_argument('name', required=True, help='优惠券名称')
coupon_parser.add_argument('quantity', required=True, help='优惠券数量')
coupon_parser.add_argument('type', required=True, help='优惠券类型: [all, assign_item, assign_items_group]')
coupon_parser.add_argument('items', required=True, help='如果type是all，那么此此段也是all； 如果是指定类型，这里为list， 放指定商品的id')

consume_coupon_parser = reqparse.RequestParser()
consume_coupon_parser.add_argument('id', required=True, help='优惠券ID')
consume_coupon_parser.add_argument('quantity', required=True, help='优惠券消费数量')
