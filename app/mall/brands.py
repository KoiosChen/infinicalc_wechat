from flask_restplus import Resource, fields, reqparse
from ..models import Brands
from . import mall
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import table_fields, new_data_obj, get_table_data
from ..decorators import permission_required
from ..swagger import head_parser, page_parser
from .mall_api import mall_ns, return_json

add_brand_parser = reqparse.RequestParser()
add_brand_parser.add_argument('name', required=True, help='品牌名')
add_brand_parser.add_argument('company_name', help='公司名')
add_brand_parser.add_argument('company_address', help='公司地址')
add_brand_parser.add_argument('logo', help='logo对应的图片文件ID')

update_brand_parser = add_brand_parser.copy()
update_brand_parser.replace_argument('name', required=False)


@mall_ns.route('/brands')
@mall_ns.expect(head_parser)
class BrandsApi(Resource):
    @mall_ns.marshal_with(return_json)
    @mall_ns.doc(body=page_parser)
    @permission_required("app.mall.brands.query_brands")
    def get(self, **kwargs):
        """
        获取全部品牌
        """
        args = page_parser.parse_args()
        return success_return(get_table_data(Brands, args))

    @mall_ns.doc(body=add_brand_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.brands.add_brand")
    def post(self, **kwargs):
        """新增品牌"""
        args = add_brand_parser.parse_args()
        brand_db = Brands.query.filter_by(name=args['name']).first()
        if brand_db:
            return false_return(message=f"<{args['name']}>已经存在"), 400

        new_one = new_data_obj("Brands", **{"name": args['name']})

        for f in ("company_name", "company_address"):
            if f in args.keys():
                setattr(new_one['obj'], f, args[f])

        return submit_return(f"品牌{args['name']}添加成功，id：{new_one['obj'].id}", f"品牌{args['name']}添加失败")



@mall_ns.route('/brands/<string:brand_id>')
@mall_ns.param('brand_id', '品牌ID')
@mall_ns.expect(head_parser)
class BrandApi(Resource):
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.brands.query_brands")
    def get(self, **kwargs):
        """
        获取指定品牌数据
        """
        fields_ = table_fields(Brands)
        b = Brands.query.get(kwargs['brand_id'])
        return success_return({f: getattr(b, f) for f in fields_}, "")

    @mall_ns.doc(body=update_brand_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.brands.update_brand")
    def put(self, **kwargs):
        """更新品牌"""
        args = update_brand_parser.parse_args()
        brand = Brands.query.get(kwargs['brand_id'])
        for k, v in args.items():
            if hasattr(brand, k) and v:
                setattr(brand, k, v)
        return success_return(message=f"品牌更新成功{args.keys()}")

    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.brands.delete_brand")
    def delete(self, **kwargs):
        """删除品牌"""
        brand = Brands.query.get(kwargs['brand_id'])
        db.session.delete(brand)
        return success_return() if session_commit() else false_return(message="删除品牌失败"), 400
