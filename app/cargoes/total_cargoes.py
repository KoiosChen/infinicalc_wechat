from flask import request
from flask_restplus import Resource, reqparse
from ..models import TotalCargoes, Permission, ExpressAddress
from . import cargoes
from app.frontstage_auth import auths
from .. import db, default_api, logger
from ..common import success_return, false_return, submit_return
from ..public_method import table_fields, get_table_data, get_table_data_by_id, new_data_obj
import datetime
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
from ..public_user_func import modify_user_profile
import requests

cargoes_ns = default_api.namespace('Total Cargoes', path='/cargoes',
                                   description='指仓储货物，例如窖藏酒，整箱货物等；都可以进行分装操作')

return_json = cargoes_ns.model('ReturnResult', return_dict)

cargo_page_parser = page_parser.copy()
cargo_page_parser.add_argument('Authorization', required=True, location='headers')


@cargoes_ns.route('')
class CargoesAPI(Resource):
    @cargoes_ns.marshal_with(return_json)
    @cargoes_ns.expect(cargo_page_parser)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """
        获取所有仓储货物清单
        """
        args = cargoes_ns.parse_args()
        if 'search' not in args.keys():
            args['search'] = {}
        args['search']['owner_id'] = kwargs['current_user'].id
        return success_return(get_table_data(TotalCargoes, args), "请求成功")
