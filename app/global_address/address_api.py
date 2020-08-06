from flask_restplus import Resource, reqparse, cors
from flask import request
from ..models import ExpressAddress
from . import global_address
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, sort_by_order
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id
from ..decorators import permission_required, allow_cross_domain
from ..swagger import return_dict, head_parser, page_parser

address_ns = default_api.namespace('global_address', path='/global_address', description='国家、省、城市、区管理接口')

return_json = address_ns.model('ReturnRegister', return_dict)