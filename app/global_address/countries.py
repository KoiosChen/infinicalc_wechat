from flask_restplus import Resource, reqparse
from ..models import Countries, Permission
from . import global_address
from ..common import success_return, false_return, submit_return
from ..public_method import get_table_data, get_table_data_by_id, new_data_obj
from ..decorators import permission_required
from ..swagger import head_parser, page_parser
from .address_api import address_ns, return_json
from .. import db, logger

add_address_parser = reqparse.RequestParser()
add_address_parser.add_argument("name", required=True, help='国家名称')
add_address_parser.add_argument('longitude', type=float, help='精度')
add_address_parser.add_argument('latitude', type=float, help='纬度')
add_address_parser.add_argument('population', type=int, help='人口')

country_page_parser = page_parser.copy()


@address_ns.route('/countries')
@address_ns.expect(head_parser)
class QueryCountries(Resource):
    @address_ns.marshal_with(return_json)
    @address_ns.doc(body=country_page_parser)
    @permission_required(["app.global_address.countries.get_all_countries", Permission.OPERATOR])
    def get(self, **kwargs):
        """
        查询所有国家列表
        """
        args = country_page_parser.parse_args()
        return success_return(get_table_data(Countries, args), "请求成功")

    @address_ns.doc(body=add_address_parser)
    @address_ns.marshal_with(return_json)
    @permission_required("app.global_address.countries.new_address")
    def post(self, **kwargs):
        """
        创建国家
        """
        args = add_address_parser.parse_args()
        new_country = new_data_obj("Countries", **{"name": args['name']})
        db.session.flush()
        if new_country:
            if not new_country['status']:
                return false_return(f"{args['name']}已存在")

            for k, v in args.items():
                if hasattr(new_country['obj'], k) and v:
                    setattr(new_country['obj'], k, v)
            return submit_return("新增国家成功", "新增国家失败")
        else:
            return false_return("新增国家失败")


@address_ns.route('/countries/<int:country_id>/provinces')
@address_ns.expect(head_parser)
@address_ns.param('country_id', '国家ID')
class AddProvinceToCountry(Resource):
    @address_ns.doc(body=add_address_parser)
    @address_ns.marshal_with(return_json)
    @permission_required("app.global_address.countries.new_province")
    def post(self, **kwargs):
        """待更新"""
        pass
