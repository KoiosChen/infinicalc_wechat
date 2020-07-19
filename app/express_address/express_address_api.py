from flask_restplus import Resource, reqparse, cors
from flask import request
from ..models import ExpressAddress
from . import express
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, sort_by_order
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id
from ..decorators import permission_required, allow_cross_domain
from ..swagger import return_dict, head_parser, page_parser

express_ns = default_api.namespace('express_address', path='/expressAddress', description='快递地址管理')

return_json = express_ns.model('ReturnRegister', return_dict)

express_page_parser = page_parser.copy()


@express_ns.route('')
@express_ns.expect(head_parser)
class QueryExpressAddress(Resource):
    @express_ns.marshal_with(return_json)
    @express_ns.doc(body=express_page_parser)
    @permission_required("app.elements.elements_api.get_elements")
    def get(self, **kwargs):
        """
        查询所有快递地址列表
        """
        args = express_page_parser.parse_args()
        return success_return(get_table_data(ExpressAddress, args, ['children']), "请求成功")
