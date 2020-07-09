from flask_restplus import Resource, fields, reqparse
from ..models import Brands, SKU, sku_standardvalue, ImgUrl, PurchaseInfo
from . import mall
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import table_fields, new_data_obj, get_table_data, get_table_data_by_id
from ..decorators import permission_required
from ..swagger import head_parser, page_parser
from .mall_api import mall_ns, return_json

add_sku_parser = reqparse.RequestParser()
add_sku_parser.add_argument('spu_id', required=True, help="")
add_sku_parser.add_argument('name', required=True, help='sku名称，例如 国行32G版本')
add_sku_parser.add_argument('price', required=True, help='SKU价格')
add_sku_parser.add_argument('discount', help='将会用Decimal处理 0 ~ 1')
add_sku_parser.add_argument('member_price', help='会员价，小于等于price')
add_sku_parser.add_argument('score_types', help='是否可以用积分 0：不可以，1：可以')
add_sku_parser.add_argument('contents', help='富文本内容')
add_sku_parser.add_argument('status', help='是否上架 1：上架 0：下架')
add_sku_parser.add_argument("unit", required=True, help='SKU单位')

update_sku_parser = add_sku_parser.copy()
update_sku_parser.replace_argument("spu_id", required=False)
update_sku_parser.replace_argument("name", required=False)
update_sku_parser.replace_argument("price", required=False)
update_sku_parser.replace_argument("unit", required=False)

standards_values_parser = reqparse.RequestParser()
standards_values_parser.add_argument('data', type=list, required=True, help='规格和对应值的列表', location='json')

sku_img_parser = reqparse.RequestParser()
sku_img_parser.add_argument('images', type=list, required=True, help='sku对应的所有图片', location='json')

add_purchase_parser = reqparse.RequestParser()
add_purchase_parser.add_argument("amount", required=True, help='进货数量')


@mall_ns.route('/sku')
@mall_ns.expect(head_parser)
class SKUApi(Resource):
    @mall_ns.marshal_with(return_json)
    @mall_ns.doc(body=page_parser)
    @permission_required("app.mall.sku.query_sku_all")
    def get(self, **kwargs):
        """
        获取全部SKU
        """
        args = page_parser.parse_args()
        return success_return(get_table_data(SKU, args, ['values', 'images']))

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
                                         "spu_id": args['spu_id'],
                                         "unit": args['unit']})
        return submit_return(f"SKU {args['name']} 添加到SPU ID: {args['spu_id']}成功，id：{new_one['obj'].id}",
                             f"SKU {args['name']} 添加失败")


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

        return success_return(get_table_data_by_id(SKU, kwargs['sku_id'], appends=['values', 'images']))

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
            return success_return("删除SKU成功") if session_commit() else false_return(message="删除SKU失败"), 400
        else:
            return false_return(message=f"<{kwargs['sku_id']}>不存在"), 400


@mall_ns.route('/sku/<string:sku_id>/standards/values')
@mall_ns.expect(head_parser)
class SKUStandardsValues(Resource):
    @mall_ns.doc(body=standards_values_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.standards.set_sku_standards_values")
    def post(self, **kwargs):
        """SKU新增规格对应的值"""
        sku_id = kwargs.get('sku_id')
        args = standards_values_parser.parse_args()
        data = args.get('data')
        sku = SKU.query.get(sku_id)
        if sku:
            for s_v in data:
                new_value = new_data_obj("StandardValue", **{"standard_id": s_v['standard'], "value": s_v["value"]})
                if new_value:
                    sku.values.append(new_value['obj'])
                else:
                    return false_return(message=f"<{sku_id}>添加规则值{s_v['standard']}失败")
            return submit_return(f"<{sku_id}>添加规则值成功", f"<{sku_id}>添加规则值失败")
        else:
            return false_return(message=f"<{sku_id}>不存在"), 400


@mall_ns.route('/sku/<string:sku_id>/images')
@mall_ns.expect(head_parser)
class SKUImages(Resource):
    @mall_ns.doc(body=sku_img_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.sku.sku_images")
    def put(self, **kwargs):
        """指定SKU上传相应的图片"""
        sku_id = kwargs.get('sku_id')
        args = sku_img_parser.parse_args()
        sku = SKU.query.get(sku_id)
        if sku:
            for img in args['images']:
                if img not in sku.images:
                    image = ImgUrl.query.get(img)
                    if image:
                        sku.images.append(image)
                    else:
                        return false_return(message="图片不存在"), 400
            return success_return(message=f"<{sku_id}>增加图片成功")
        else:
            return false_return(message=f"<{sku_id}>不存在"), 400


@mall_ns.route('/sku/<string:sku_id>/purchase_info')
@mall_ns.param('sku_id', "SKU ID")
@mall_ns.expect(head_parser)
class SKUPurchase(Resource):
    @mall_ns.doc(body=add_purchase_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.sku.add_purchase_info")
    def post(self, **kwargs):
        """根据sku进货"""
        sku_id = kwargs.get("sku_id")
        args = add_purchase_parser.parse_args()
        sku = SKU.query.get(sku_id)
        if sku and not sku.status:
            new_one = new_data_obj("PurchaseInfo", **{"sku_id": sku_id,
                                                      "amount": eval(args['amount']),
                                                      "operator": kwargs['info']['user'].id})
            if new_one:
                sku.quantity += eval(args['amount'])
                db.session.add(sku)
                db.session.flush()
                return submit_return(f"进货单<{new_one['obj'].id}>新增成功，<{sku.name}>增加数量<{args['amount']}>, 共<{sku.quantity}>",
                                     f"进货单<{new_one['obj'].id}>新增成功，SKU数量增加失败")
            else:
                false_return(message="进货数据添加失败"), 400
        elif sku and sku.status:
            return false_return(message=f"SKU <{sku.id}> 目前是上架状态，无法增加进货单，请先下架"), 400
        else:
            return false_return(message=f"<{sku_id}>不存在"), 400
