from flask_restplus import Resource, fields, reqparse
from ..models import SPU, Standards
from . import mall
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
from ..public_method import table_fields, new_data_obj
from ..decorators import permission_required
from ..swagger import head_parser
from .mall_api import mall_ns, return_json

add_standard_parser = reqparse.RequestParser()
add_standard_parser.add_argument('name', required=True, help='规格名称')

update_standard_parser = add_standard_parser.copy()
update_standard_parser.replace_argument('name', required=False)


@mall_ns.route('/standards')
@mall_ns.expect(head_parser)
class StandardsApi(Resource):
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.standards.query_standards")
    def get(self, **kwargs):
        """
        获取全部规格
        """
        fields_ = table_fields(Standards)
        r = [{f: getattr(p, f) for f in fields_} for p in Standards.query.all()]
        return success_return(r, "")

    @mall_ns.doc(body=add_standard_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.standards.add_standard")
    def post(self, **kwargs):
        """新增产品规格"""
        args = add_standard_parser.parse_args()
        standard_db = Standards.query.filter_by(name=args['name']).first()
        if standard_db:
            return false_return(message=f"<{args['name']}>已经存在产品规格中"), 400

        new_one = new_data_obj("Standards", **{"name": args['name']})

        return success_return(message=f"产品规格<{args['name']}>添加成功，id：{new_one['obj'].id}")
