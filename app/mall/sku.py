from flask_restplus import Resource, fields, reqparse
from ..models import Brands, SKU, sku_standardvalue
from . import mall
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
from ..public_method import table_fields, new_data_obj
from ..decorators import permission_required
from ..swagger import head_parser
from .mall_api import mall_ns, return_json
from decimal import Decimal

add_sku_parser = reqparse.RequestParser()
add_sku_parser.add_argument('spu_id', required=True, help="")
add_sku_parser.add_argument('name', required=True, help='sku名称，例如 国行32G版本')
add_sku_parser.add_argument('price', required=True, help='SKU价格')
add_sku_parser.add_argument('discount', help='将会用Decimal处理 0 ~ 1')
add_sku_parser.add_argument('member_price', help='会员价，小于等于price')
add_sku_parser.add_argument('score_types', help='是否可以用机房0：不可以，1：可以')
add_sku_parser.add_argument('contents', help='富文本内容')
add_sku_parser.add_argument('status', help='是否上架 1：上架 0：下架')

update_sku_parser = add_sku_parser.copy()
update_sku_parser.replace_argument("spu_id", required=False)
update_sku_parser.replace_argument("name", required=False)
update_sku_parser.replace_argument("price", required=False)

standards_values_parser = reqparse.RequestParser()
standards_values_parser.add_argument('data', type=list, required=True, help='规格和对应值的列表', location='json')


@mall_ns.route('/sku')
@mall_ns.expect(head_parser)
class SKUApi(Resource):
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.sku.query_sku_all")
    def get(self, **kwargs):
        """
        获取全部SKU
        """
        fields_ = table_fields(SKU)
        fields_.extend(["values", "images"])
        r = list()
        for p in SKU.query.all():
            tmp = dict()
            for f in fields_:
                v = getattr(p, f)
                if f in ['price', 'discount', 'member_price', 'create_at', 'update_at']:
                    tmp[f] = str(v)
                elif f in ['values', 'images']:
                    tmp1 = list()
                    t1 = getattr(p, f)
                    for value in t1:
                        tmp1.append({'id': value.id, 'path': value.path, 'type': value.attribute})
                    tmp[f] = tmp1
                else:
                    tmp[f] = getattr(p, f)
            r.append(tmp)
        return success_return(r, "")

    @mall_ns.doc(body=add_sku_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.sku.add_sku")
    def post(self, **kwargs):
        """新增SKU"""
        args = add_sku_parser.parse_args()
        sku_db = SKU.query.filter_by(spu_id=args['spu_id'], name=args['name']).first()
        if sku_db:
            return false_return(message=f"<{args['name']}>已经存在其对应的SPU中")

        new_one = new_data_obj("SKU", **{"name": args['name'],
                                         "price": args['price'],
                                         "discount": args['discount'],
                                         "member_price": args['member_price'],
                                         "score_types": args['score_types'],
                                         "contents": args['contents'],
                                         "status": args['status'],
                                         "spu_id": args['spu_id']})
        return success_return(message=f"SKU {args['name']} 添加到SPU ID: {args['spu_id']}成功，id：{new_one.id}")


@mall_ns.route('/sku/<string:sku_id>')
@mall_ns.param('sku_id', 'SKU ID')
@mall_ns.expect(head_parser)
class PerSKUApi(Resource):
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.sku.query_per_sku")
    def get(self, **kwargs):
        """
        获取指定sku数据
        """
        fields_ = table_fields(SKU)
        fields_.extend(["values", "images"])
        tmp = dict()
        p = SKU.query.get(kwargs.get('sku_id'))
        for f in fields_:
            v = getattr(p, f)
            if f in ['price', 'discount', 'member_price', 'create_at', 'update_at']:
                tmp[f] = str(v)
            elif f == 'images':
                tmp1 = list()
                t1 = getattr(p, f)
                for value in t1:
                    tmp1.append({'image_id': value.id, 'path': value.path, 'type': value.attribute})
                tmp[f] = tmp1
            elif f == 'values':
                tmp1 = list()
                t1 = getattr(p, f)
                for value in t1:
                    tmp1.append({'value_id': value.id, 'value': value.value, 'standard': value.standards.name})
                tmp[f] = tmp1
            else:
                tmp[f] = getattr(p, f)
        return success_return(tmp, "")

    @mall_ns.doc(body=update_sku_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.sku.update_sku")
    def put(self, **kwargs):
        """更新SKU"""
        args = update_sku_parser.parse_args()
        sku = SKU.query.get(kwargs['sku_id'])
        for k, v in args.items():
            if hasattr(sku, k) and v:
                setattr(sku, k, v)
            else:
                continue
        return success_return(message=f"SKU更新成功{args.keys()}")

    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.brands.delete_brand")
    def delete(self, **kwargs):
        """删除SKU"""
        sku = SKU.query.get(kwargs['sku_id'])
        if sku:
            db.session.delete(sku)
            return success_return("删除SKU成功") if session_commit() else false_return(message="删除SKU失败")
        else:
            return false_return(message=f"<{kwargs['sku_id']}>不存在")


@mall_ns.route('/sku/<string:sku_id>/standards/values')
@mall_ns.expect(head_parser)
class SKUStandardsValues(Resource):
    @mall_ns.doc(body=standards_values_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.standards.set_sku_standards_values")
    def put(self, **kwargs):
        """SKU新增规格对应的值"""
        sku_id = kwargs.get('sku_id')
        args = standards_values_parser.parse_args()
        data = args.get('data')
        sku = SKU.query.get(sku_id)
        if sku:
            for s_v in data:
                new_value = new_data_obj("StandardValue", **{"standard_id": s_v['standard'], "value": s_v["value"]})
                sku.values.append(new_value)
            return success_return(message=f"<{sku_id}>添加规则值成功")
        else:
            return false_return(message=f"<{sku_id}>不存在")
