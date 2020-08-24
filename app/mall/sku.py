from flask_restplus import Resource, fields, reqparse
from ..models import Brands, SKU, sku_standardvalue, PurchaseInfo, Permission
from . import mall, image_operate
from .. import db, redis_db, default_api, logger, sku_lock
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import table_fields, new_data_obj, get_table_data, get_table_data_by_id
from ..decorators import permission_required
from ..swagger import head_parser, page_parser
from .mall_api import mall_ns, return_json
import uuid
import threading
import json

add_sku_parser = reqparse.RequestParser()
add_sku_parser.add_argument('spu_id', required=True, help="", location='json')
add_sku_parser.add_argument('name', required=True, help='sku名称，例如 国行32G版本', location='json')
add_sku_parser.add_argument('price', required=True, help='SKU价格', location='json')
add_sku_parser.add_argument('discount', help='将会用Decimal处理 0 ~ 1', location='json')
add_sku_parser.add_argument('member_price', help='会员价，小于等于price', location='json')
add_sku_parser.add_argument('score_type', help='是否可以用积分 0：不可以，1：可以', location='json')
add_sku_parser.add_argument('contents', help='富文本内容', location='json')
add_sku_parser.add_argument('status', type=int, choices=[0, 1], help='是否上架 1：上架 0：下架')
add_sku_parser.add_argument("unit", required=True, help='SKU单位', location='json')
add_sku_parser.add_argument('objects', type=list, help='sku对应的所有图片或视频', location='json')
add_sku_parser.add_argument('agent_first_rebate', type=float, help='一级代理返佣金额（元）')
add_sku_parser.add_argument('agent_second_rebate', type=float, help='二级代理返佣金额（元)')
add_sku_parser.add_argument('could_get_coupon_id', help='购买成功后可获取的优惠券', location='json')
add_sku_parser.add_argument('score', type=int, help='购买成功后可获取的积分')

update_sku_parser = add_sku_parser.copy()
update_sku_parser.replace_argument("spu_id", required=False, location='json')
update_sku_parser.replace_argument('name', help='sku名称，例如 国行32G版本', required=False, location='json')
update_sku_parser.replace_argument('price', help='SKU价格', required=False, location='json')
update_sku_parser.replace_argument("unit", help='SKU单位', required=False, location='json')

standards_values_parser = reqparse.RequestParser()
standards_values_parser.add_argument('data', type=list, required=True,
                                     help='规格和对应值的列表，例如[{"standard": standard_id, "value": 11}]', location='json')

sku_img_parser = reqparse.RequestParser()
sku_img_parser.add_argument('objects', type=list, required=True, help='sku对应的所有图片或视频', location='json')

add_purchase_parser = reqparse.RequestParser()
add_purchase_parser.add_argument("amount", required=True, help='进货数量', location='json')

sku_page_parser = page_parser.copy()
sku_page_parser.add_argument('home_page', help='搜索是否需要首页加载', type=int, choices=[0, 1], location='args')

temporary_cart_parser = reqparse.RequestParser()
temporary_cart_parser.add_argument('quantity', type=int, required=True, help='购买数量')
temporary_cart_parser.add_argument('combo', help='如果此SKU有关联的套餐，则让用户选择套餐种类，价格按照套餐价格计算并显示。传benefits id')
temporary_cart_parser.add_argument('packing_order_id', help='如果在分装流程中，此参数必传，通过接口获取预分配的分装ID')


def compute_quantity(sku_id, quantity_change):
    sku = SKU.query.get(sku_id) if isinstance(sku_id, str) else sku_id
    logger.debug(str(sku))
    if not sku:
        raise Exception(f"没有{sku_id}对应的记录")
    # 无论quantity_change是整数还是负数
    if (sku.quantity + quantity_change) >= 0:
        logger.debug(f"{sku.quantity} + {quantity_change}")
        sku.quantity += quantity_change
        logger.debug(sku.quantity)
        db.session.add(sku)
        logger.debug("db flushed")
        return success_return()
    else:
        logger.error(f'sku库存不足。 库存{sku.quantity}, 采购量为{abs(quantity_change)}')
        if isinstance(sku_id, str):
            raise Exception(f'sku库存不足。 库存{sku.quantity}, 采购量为{abs(quantity_change)}')
        else:
            return false_return()


def thread_compute_quantity(sku_id, operate_key, lock, quantity_change):
    if lock.acquire():
        try:
            compute_quantity(sku_id, quantity_change)
            if session_commit().get('code') == 'false':
                raise Exception(f"变更sku{sku_id}数量失败")
        except Exception as e:
            logger.error(str(e))
            redis_db.set(f"change_sku_quantity::{sku_id}::{operate_key}",
                         json.dumps(false_return(message=str(e))),
                         ex=6000)
        finally:
            lock.release()


def change_sku_quantity(sku_id, lock, quantity_change):
    operate_key = str(uuid.uuid4())
    sku_thread = threading.Thread(target=thread_compute_quantity, args=(sku_id, operate_key, lock, quantity_change))
    sku_thread.start()
    sku_thread.join()
    k = f"change_sku_quantity::{sku_id}::{operate_key}"
    if redis_db.exists(k):
        result = json.loads(redis_db.get(k))
        redis_db.delete(k)
        return result
    else:
        return success_return(message=f"sku数量改变成功")


@mall_ns.route('/sku')
@mall_ns.expect(head_parser)
class SKUApi(Resource):
    @mall_ns.marshal_with(return_json)
    @mall_ns.doc(body=sku_page_parser)
    @permission_required("app.mall.sku.query_sku_all")
    def get(self, **kwargs):
        """
        获取全部SKU
        """
        args = sku_page_parser.parse_args()
        args['search'] = dict()
        if args.get("home_page") in [0, 1]:
            args['search']['home_page'] = args.get('home_page')
        return success_return(get_table_data(SKU, args, ['values', 'objects']))

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
                                         "score_type": args['score_type'],
                                         "contents": args['contents'],
                                         "status": args['status'],
                                         "spu_id": args['spu_id'],
                                         "unit": args['unit']})
        if args['objects']:
            append_image = image_operate.operate(new_one['obj'], args['objects'], "append")
            if append_image.get("code") == 'success':
                return submit_return(f"SKU {args['name']} 添加到SPU ID: {args['spu_id']}成功，id：{new_one['obj'].id}",
                                     f"SKU {args['name']} 添加失败")
            else:
                return false_return("图片添加失败")
        else:
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
        return success_return(
            get_table_data_by_id(SKU, kwargs['sku_id'], appends=['values', 'objects', 'sku_promotions']))

    @mall_ns.doc(body=update_sku_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.sku.update_sku")
    def put(self, **kwargs):
        """更新SKU"""
        args = update_sku_parser.parse_args()
        sku = SKU.query.get(kwargs['sku_id'])
        for k, v in args.items():
            if k == 'objects':
                image_operate.operate(obj=sku, imgs=args[k], action="append")
                continue

            if k == 'name' and SKU.query.filter_by(spu_id=args['spu_id'], name=args['name']).first():
                return false_return(message=f"<{args['name']}>已经存在其对应的SPU中")

            if hasattr(sku, k) and v:
                setattr(sku, k, v)

        return submit_return(f"SKU更新成功{args.keys()}", f"SKU更新失败{args.keys()}")

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


@mall_ns.route('/sku/<string:sku_id>/shopping_cart')
@mall_ns.expect(head_parser)
class SKUAddToShoppingCart(Resource):
    @mall_ns.doc(body=temporary_cart_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def post(self, **kwargs):
        """SKU添加到购物车中"""
        sku_id = kwargs.get('sku_id')
        args = temporary_cart_parser.parse_args()
        current_user = kwargs.get('current_user')
        sku = SKU.query.get(sku_id)
        if sku and sku.status == 1 and sku.delete_at is None:
            if args.get("combo"):
                cart_item = new_data_obj("ShoppingCart", **{"customer_id": current_user.id, "sku_id": sku_id,
                                                            "combo": args.get('combo')})
            else:
                cart_item = new_data_obj("ShoppingCart", **{"customer_id": current_user.id, "sku_id": sku_id})

            if cart_item:
                if cart_item['status']:
                    cart_item['obj'].quantity = args['quantity']
                else:
                    cart_item['obj'].quantity += args['quantity']

                # 如果是分装流程，那么就添加上packing_order到购物车商品上，表示特殊商品
                if args.get('packing_order'):
                    cart_item['obj'].packing_item_order = args.get('packing_order')
                return submit_return("购物车添加成功", "购物出添加失败")
            else:
                return false_return(message=f"将<{sku_id}>添加规到购物车失败"), 400
        else:
            return false_return(message=f"<{sku_id}>已下架"), 400


@mall_ns.route('/sku/<string:sku_id>/images')
@mall_ns.expect(head_parser)
class SKUImages(Resource):
    @mall_ns.doc(body=sku_img_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.sku.sku_objects")
    def put(self, **kwargs):
        """指定SKU上传相应的图片"""
        sku_id = kwargs.get('sku_id')
        args = sku_img_parser.parse_args()
        sku = SKU.query.get(sku_id)
        return image_operate.operate(obj=sku, imgs=args['objects'], action="append")

    def delete(self, **kwargs):
        """指定SKU 删除相应图片"""
        sku_id = kwargs.get('sku_id')
        args = sku_img_parser.parse_args()
        sku = SKU.query.get(sku_id)
        return image_operate.operate(obj=sku, imgs=args['objects'], action="remove")


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
                # sku.quantity += eval(args['amount'])
                change_result = change_sku_quantity(sku_id, sku_lock, eval(args['amount']))
                if change_result.get("code") == "false":
                    return change_result, 400
                return submit_return(
                    f"进货单<{new_one['obj'].id}>新增成功，<{sku.name}>增加数量<{args['amount']}>, 共<{sku.quantity}>",
                    f"进货单<{new_one['obj'].id}>新增成功，SKU数量增加失败")
            else:
                false_return(message="进货数据添加失败"), 400
        elif sku and sku.status:
            return false_return(message=f"SKU <{sku.id}> 目前是上架状态，无法增加进货单，请先下架"), 400
        else:
            return false_return(message=f"<{sku_id}>不存在"), 400
