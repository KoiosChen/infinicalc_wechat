from flask_restplus import Resource, fields, reqparse
from ..models import Brands
from . import mall
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import table_fields, new_data_obj, get_table_data, get_table_data_by_id
from ..decorators import permission_required
from ..swagger import head_parser, page_parser
from .mall_api import mall_ns, return_json

add_brand_parser = reqparse.RequestParser()
add_brand_parser.add_argument('name', required=True, help='品牌名')
add_brand_parser.add_argument('company_name', help='公司名')
add_brand_parser.add_argument('company_address', help='公司地址')
add_brand_parser.add_argument('logo', help='logo对应obj_storage ID')

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
        new_one = new_data_obj("Brands", **{"name": args['name']})

        if new_one:
            if not new_one.get('status'):
                return false_return(message=f"<{args['name']}>已经存在"), 400
            else:
                for k, v in args.items():
                    if hasattr(new_one['obj'], k) and v:
                        setattr(new_one['obj'], k, v)

                return submit_return(f"品牌{args['name']}添加成功，id：{new_one['obj'].id}", f"品牌{args['name']}添加失败")
        else:
            return false_return(message=f"品牌{args['name']}添加失败"), 400


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
        return success_return(get_table_data_by_id(Brands, kwargs['brand_id']))

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
        return submit_return(f"品牌更新成功{args.keys()}", f"品牌更新失败{args.keys()}")

    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.brands.delete_brand")
    def delete(self, **kwargs):
        """删除品牌"""
        brand = Brands.query.get(kwargs['brand_id'])
        if brand and not brand.spu.all():
            db.session.delete(brand)
            return submit_return(f"删除品牌{kwargs['brand_id']}成功", f"删除品牌{kwargs['brand_id']}失败")
        else:
            return false_return(message=f"删除品牌{kwargs['brand_id']}失败，此品牌被占用{brand.spu.all()}")


@mall_ns.route('/brands/<string:brand_id>/items')
@mall_ns.param('brand_id', '品牌ID')
@mall_ns.expect(head_parser)
class BrandItemsApi(Resource):
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.brands.query_brand_items")
    def get(self, **kwargs):
        """
        获取指定分类的所有商品信息
        """
        return success_return(get_table_data_by_id(Brands, kwargs['brand_id'], ['spu']))
