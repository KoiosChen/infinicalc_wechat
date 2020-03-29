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

cart_add_parser = reqparse.RequestParser()
cart_add_parser.add_argument('id', required=True, help='商品ID')
cart_add_parser.add_argument('quantity', required=True, help='商品数量')
cart_add_parser.add_argument('product_options', required=True, help='商品选项： list， 选项表中的id')
