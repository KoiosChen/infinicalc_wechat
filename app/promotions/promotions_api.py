from flask_restplus import Resource, reqparse
from ..models import Promotions
from .. import default_api, logger
from ..common import success_return, false_return, session_commit
from ..public_method import new_data_obj, get_table_data
from ..decorators import permission_required
import datetime
from ..swagger import return_dict, head_parser, page_parser
from app.type_validation import *
from .operate_promotions import AddPromotions

promotions_ns = default_api.namespace('promotions', path='/promotions', description='包括促销活动设置相关操作')

return_json = promotions_ns.model('ReturnRegister', return_dict)

add_promotion_parser = reqparse.RequestParser()
add_promotion_parser.add_argument('name', required=True, help='活动名称，唯一性约束')
# add_promotion_parser.add_argument('promotion_type', required=True, type=int,
#                                   help='0: 满减，1：满赠，2：满折，3：加价购，4：套餐，5：预售, 6：秒杀, 7: 优惠券')
add_promotion_parser.add_argument('group', required=True, help='促销活动组ID, 在促销活动组接口添加。group_id 为-1表示是发优惠券，>=0的group，为活动')
add_promotion_parser.add_argument('first_order', type=int, choices=[0, 1], default=0, help='是否是首单参与，0否，1是, 不传为0')
add_promotion_parser.add_argument('reject_coupon', type=int, choices=[0, 1], default=0, help='是否和优惠券冲突，0否，1是， 不传为0')
add_promotion_parser.add_argument('customer_level', type=int, default=1, help='可参与用户等级，1为最低，默认为1')
add_promotion_parser.add_argument('gender', type=int, choices=[0, 1, 2], default=0, help='可参与性别，0为都可以，1为男性、2为女性')
add_promotion_parser.add_argument('age_min', type=int, default=0, help='最小可参与年龄，默认为0')
add_promotion_parser.add_argument('age_max', type=int, default=200, help='最大可参与年龄，默认为200')
add_promotion_parser.add_argument('accumulation', type=int, choices=[0, 1], default=0,
                                  help='是否允许累积，默认为0，不允许。如果允许累加则为1。如果可以累加，则利益规则数量会大于. 默认为0')
add_promotion_parser.add_argument('scope', type=int, choices=[0, 1, 2], default=1, help='0：非全场，1: 全场， 2：线下, 默认为1')
add_promotion_parser.add_argument('with_special', type=int, choices=[0, 1], default=0,
                                  help='1: 可用于特价商品 0: 不能。默认不能(商品优惠卷除外)')
add_promotion_parser.add_argument('start_time', required=True, type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d %H:%M:%S'),
                                  help='活动开始时间')
add_promotion_parser.add_argument('end_time', required=True, type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d %H:%M:%S'),
                                  help='活动结束时间')
add_promotion_parser.add_argument('brands', type=list, help='参与活动的品牌,传递brands表的ID, 可为空[]', location='json',
                                  default=[{}])
add_promotion_parser.add_argument('classifies', type=list, help='参与活动的分类,传递classifies表的ID, 可为空[]', location='json',
                                  default=[{}])
add_promotion_parser.add_argument('spu', type=list, help='参与活动的SPU,传递spu表的ID, 可为空[]', location='json', default=[{}])
add_promotion_parser.add_argument('sku', type=list, help='参与活动的SKU,传递sku表的ID, 可为空[]', location='json', default=[{}])

add_enough_reduce_parser = add_promotion_parser.copy()
add_enough_reduce_parser.add_argument('benefits', required=True, type=enough_reduce_type, location='json', default=[{}],
                                      help='如果accumulation为1，则允许传递多个. list中json为：'
                                           '{"with_amount": int, "reduced_amount": int}')

add_enough_gifts_parser = add_promotion_parser.copy()
add_enough_gifts_parser.add_argument('benefits', required=True, type=enough_gifts_type, location='json', default=[{}],
                                     help="如果accumulation为1，则允许传递多个. list中json为: "
                                          "{'with_quantity': {'need_one': True, 'type': int}, '"
                                          "'with_amount': {'need_one': True, 'type': int}, "
                                          "'free_quantity': {'required': True, 'type': int}, "
                                          "'gifts': {'required': True, 'type': list}}")

add_pay_more_parser = add_promotion_parser.copy()
add_pay_more_parser.add_argument('benefits', required=True, type=enough_pay_more_type, location='json', default=[{}],
                                 help="accumulation为0，list中只允许传一个json. list中json为："
                                      "{'with_amount': {'required': True, 'type': int},"
                                      " 'pay_more_quantity': {'type': int},"
                                      " 'gifts': {'required': True, 'type': list}}")
add_pay_more_parser.remove_argument('accumulation')

add_combo_parser = add_promotion_parser.copy()
add_combo_parser.add_argument('benefits', required=True, type=combo_type, location='json', default=[{}],
                              help='accumulation为1，list中只允许多个json. list中json为：'
                                   '{"combo_price": float, "gifts": list}')
add_combo_parser.remove_argument('accumulation')
add_combo_parser.remove_argument('brands')
add_combo_parser.remove_argument('classifies')
add_combo_parser.remove_argument('spu')

add_presell_parser = add_promotion_parser.copy()
add_presell_parser.add_argument('benefits', required=True, type=presell_type, location='json', default=[{}],
                                help='accumulation为0，list中只允许传一个json. list中json为： '
                                     '{"presell_price": float, "presell_multiple": float}')
add_presell_parser.remove_argument('accumulation')
add_presell_parser.remove_argument('brands')
add_presell_parser.remove_argument('classifies')
add_presell_parser.remove_argument('spu')

add_seckill_parser = add_promotion_parser.copy()
add_seckill_parser.replace_argument('sku', required=True, type=seckill_type, location='json', default=[{}],
                                    help='[{"id": str, "seckill_price": float, "per_user": int}]')
add_seckill_parser.remove_argument('accumulation')
add_seckill_parser.remove_argument('brands')
add_seckill_parser.remove_argument('classifies')
add_seckill_parser.remove_argument('spu')
add_seckill_parser.remove_argument('benefits')

add_coupon_parser = add_promotion_parser.copy()
add_coupon_parser.remove_argument('reject_coupon')
add_coupon_parser.remove_argument('accumulation')
add_coupon_parser.remove_argument('brands')
add_coupon_parser.remove_argument('classifies')
add_coupon_parser.remove_argument('spu')
add_coupon_parser.remove_argument('group')
add_coupon_parser.add_argument('icon', help='优惠券图片')
add_coupon_parser.add_argument('desc', help='优惠券说明')
add_coupon_parser.add_argument('quota', required=True, type=int, help='优惠券发放数量')
add_combo_parser.add_argument('per_user', required=True, default=1, type=int, help='每用户允许领取数量')
add_coupon_parser.add_argument('valid_type', required=True, default=2, type=int, choices=[1, 2],
                               help='时效:1绝对时效（领取后XXX-XXX时间段有效）  2相对时效（领取后N天有效）')
add_coupon_parser.add_argument('valid_days', default=1, type=int, help='自领取之日起有效天数')
add_coupon_parser.add_argument('absolute_date', type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d %H:%M:%S'),
                               help='优惠券的绝对结束日期，当valid_type为1时，此项不能为空')

add_coupon_reduce_parser = add_coupon_parser.copy()
add_coupon_reduce_parser.add_argument('benefits', required=True, type=enough_reduce_type, location='json', default=[{}],
                                      help='{"with_amount": int, "reduced_amount": int}')

add_coupon_gifts_parser = add_coupon_parser.copy()
add_coupon_gifts_parser.add_argument('benefits', required=True, type=enough_gifts_type, location='json', default=[{}],
                                     help="{'with_amount': {'need_one': True, 'type': int}, "
                                          "'free_quantity': {'required': True, 'type': int}, "
                                          "'gifts': {'required': True, 'type': list}}")


def _add(args):
    new_one = AddPromotions(args)
    new_base = new_one.new_base_promotion()
    if new_base.get('code') == 'success':
        new_one.new_scopes()
        new_one.new_benefits()
        return success_return(message="活动新增成功") if session_commit() else false_return(message="活动新增失败")
    else:
        return new_base


def _coupons():
    pass


@promotions_ns.route('')
@promotions_ns.expect(head_parser)
class QueryPromotions(Resource):
    @promotions_ns.marshal_with(return_json)
    @promotions_ns.doc(body=page_parser)
    @permission_required("app.promotions.promotions_api.query_promotions_all")
    def get(self, **kwargs):
        """
        查询所有promotions列表
        """
        args = page_parser.parse_args()
        return success_return(get_table_data(Promotions, args['page'], args['current'], args['size']), "请求成功")


@promotions_ns.route('/enough_reduce')
@promotions_ns.expect(head_parser)
class EnoughReduce(Resource):
    @promotions_ns.doc(body=add_enough_reduce_parser)
    @promotions_ns.marshal_with(return_json)
    @permission_required("app.promotions.promotions_api.enough_reduce")
    def post(self, **kwargs):
        """添加满减活动"""
        args = add_enough_reduce_parser.parse_args(strict=True)
        logger.debug(f'>>>> Enough reduce promotion args: {args}')
        args['promotion_type'] = 0
        return _add(args)


@promotions_ns.route('/enough_gifts')
@promotions_ns.expect(head_parser)
class EnoughGifts(Resource):
    @promotions_ns.doc(body=add_enough_gifts_parser)
    @promotions_ns.marshal_with(return_json)
    @permission_required("app.promotions.promotions_api.enough_gifts")
    def post(self, **kwargs):
        """添加满赠活动"""
        args = add_enough_gifts_parser.parse_args(strict=True)
        logger.debug(f'>>>> Enough gifts promotion args: {args}')
        args['promotion_type'] = 1
        return _add(args)


@promotions_ns.route('/pay_more')
@promotions_ns.expect(head_parser)
class PayMore(Resource):
    @promotions_ns.doc(body=add_pay_more_parser)
    @promotions_ns.marshal_with(return_json)
    @permission_required("app.promotions.promotions_api.pay_more")
    def post(self, **kwargs):
        """添加加价购活动"""
        args = add_pay_more_parser.parse_args(strict=True)
        logger.debug(f'>>>> Pay more promotion args: {args}')
        args['promotion_type'] = 3
        return _add(args)


@promotions_ns.route('/combo')
@promotions_ns.expect(head_parser)
class Combo(Resource):
    @promotions_ns.doc(body=add_combo_parser)
    @promotions_ns.marshal_with(return_json)
    @permission_required("app.promotions.promotions_api.combo")
    def post(self, **kwargs):
        """添加套餐活动"""
        args = add_combo_parser.parse_args(strict=True)
        logger.debug(f'>>>> Combo promotion args: {args}')
        args['promotion_type'] = 4
        args['accumulation'] = 1
        return _add(args)


@promotions_ns.route('/presell')
@promotions_ns.expect(head_parser)
class Presell(Resource):
    @promotions_ns.doc(body=add_presell_parser)
    @promotions_ns.marshal_with(return_json)
    @permission_required("app.promotions.promotions_api.presell")
    def post(self, **kwargs):
        """添加预售活动"""
        args = add_presell_parser.parse_args(strict=True)
        logger.debug(f'>>>> Presell promotion args: {args}')
        args['promotion_type'] = 5
        return _add(args)


@promotions_ns.route('/seckill')
@promotions_ns.expect(head_parser)
class Seckill(Resource):
    @promotions_ns.doc(body=add_seckill_parser)
    @promotions_ns.marshal_with(return_json)
    @permission_required("app.promotions.promotions_api.seckill")
    def post(self, **kwargs):
        """添加秒杀活动"""
        args = add_seckill_parser.parse_args(strict=True)
        logger.debug(f'>>>> Presell promotion args: {args}')
        args['promotion_type'] = 6
        return _add(args)


@promotions_ns.route('/coupons/reduce')
@promotions_ns.expect(head_parser)
class CouponsReduce(Resource):
    @promotions_ns.doc(body=add_coupon_reduce_parser)
    @promotions_ns.marshal_with(return_json)
    @permission_required("app.promotions.promotions_api.coupons_reduce")
    def post(self, **kwargs):
        """添加满减优惠券"""
        args = add_coupon_reduce_parser.parse_args(strict=True)
        logger.debug(f'>>>> Coupon reduce promotion args: {args}')
        args['promotion_type'] = 7
        args['group'] = new_data_obj('PromotionGroups', **{'group_id': -1})['obj'].id
        new_one = AddPromotions(args)
        new_base = new_one.new_base_promotion()
        if new_base.get('code') == 'success':
            new_one.new_scopes()
            new_one.new_benefits()
            new_one.new_coupons()
            return success_return(message="活动新增成功") if session_commit() else false_return(message="活动新增失败")
        else:
            return new_base


@promotions_ns.route('/coupons/gifts')
@promotions_ns.expect(head_parser)
class CouponsGifts(Resource):
    @promotions_ns.doc(body=add_coupon_gifts_parser)
    @promotions_ns.marshal_with(return_json)
    @permission_required("app.promotions.promotions_api.coupons_gifts")
    def post(self, **kwargs):
        """添加满增优惠券， 如果要设置实物礼品券，可设置满0元赠送，商品对象都为空，直接在benefit表中添加gifts"""
        args = add_coupon_gifts_parser.parse_args(strict=True)
        logger.debug(f'>>>> Coupon gifts promotion args: {args}')
        args['promotion_type'] = 8
        args['group'] = new_data_obj('PromotionGroups', **{'group_id': -1})['obj'].id
        new_one = AddPromotions(args)
        new_base = new_one.new_base_promotion()
        if new_base.get('code') == 'success':
            new_one.new_scopes()
            new_one.new_benefits()
            new_one.new_coupons()
            return success_return(message="活动新增成功") if session_commit() else false_return(message="活动新增失败")
        else:
            return new_base
