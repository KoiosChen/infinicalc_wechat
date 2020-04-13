from flask import jsonify, request
from flask_restplus import Resource, fields, reqparse
from ..models import Users, Coupons
from . import mall
from app.auth import auths
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
import datetime
from ..decorators import permission_required
from ..swagger import return_dict, head_parser
from .mall_api import mall_ns, return_json
from ..public_method import get_table_data, new_data_obj, table_fields

add_coupon_parser = reqparse.RequestParser()
add_coupon_parser.add_argument('name', required=True, help='优惠券名称')
add_coupon_parser.add_argument('icon', required=True, help='优惠券图片，传递图片上传后的ID')
add_coupon_parser.add_argument('used_in', type=int, required=True,
                               help='使用范围，传递整数。'
                                    '例如：10：店铺优惠券，11：新人店铺券 (10, 11目前用不到）。'
                                    '20：商品优惠券（针对SKU），30：类目优惠券（针对SPU），40：分类优惠券（针对Classifies的ID）'
                                    '60：平台优惠券，61：新人平台券')
add_coupon_parser.add_argument('coupon_type', required=True, type=int, help='1满减券 2叠加满减券 3无门槛券.（需要限制大小）')
add_coupon_parser.add_argument('with_special', type=int, help='是否可用于特价商品，若不传递则为默认值：非特价商品。0：非特价，1：特价')
add_coupon_parser.add_argument('with_sn', required=True, help='店铺、分类、SPU、SKU的ID， 结合used_in字段进行区分')
add_coupon_parser.add_argument('with_amount', type=int, help='如果是满减券，则这里设置满多少金额可使用')
add_coupon_parser.add_argument('used_amount', type=int, required=True, help='券的使用金额')
add_coupon_parser.add_argument('quota', required=True, type=int, help='发券总量，不小于1')
add_coupon_parser.add_argument('start_time', type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d %H:%M:%S'),
                               required=True, help='发券开始时间, 格式%Y-%m-%d %H:%M:%S')
add_coupon_parser.add_argument('end_time', type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d %H:%M:%S'),
                               required=True, help='发券结束时间，格式%Y-%m-%d %H:%M:%S')
add_coupon_parser.add_argument('valid_type', type=int, help='时效:1绝对时效（领取后XXX-XXX时间段有效), 2相对时效（领取后N天有效）。若不传递则默认为2')
add_coupon_parser.add_argument('valid_days', type=int, help='自领取之日起有效天数')

consume_coupon_parser = reqparse.RequestParser()
consume_coupon_parser.add_argument('id', required=True, help='优惠券ID')
consume_coupon_parser.add_argument('quantity', required=True, help='优惠券消费数量')


@mall_ns.route('/coupons')
@mall_ns.expect(head_parser)
class CouponsApi(Resource):
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.coupons.query_coupons")
    def get(self, **kwargs):
        """
        获取全部优惠券
        """
        return success_return(data=get_table_data(Coupons))

    @mall_ns.doc(body=add_coupon_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.coupons.add_coupon")
    def post(self, **kwargs):
        """新增优惠券"""
        args = add_coupon_parser.parse_args()
        name = args.get('name')
        # icon = args.get('icon')
        used_in = args.get('used_in')
        # coupon_type = args.get('coupon_type')
        # with_special = args.get('with_special')
        # with_sn = args.get('with_sn')
        # with_amount = args.get('with_amount')
        # used_amount = args.get('used_amount')
        # quota = args.get('quota')
        # start_time = args.get('start_time')
        # stop_time = args.get('stop_time')
        # valid_type = args.get('valid_type')
        # valid_days = args.get('valid_days')
        new_coupon = new_data_obj('Coupons', **{"name": name, "used_in": used_in})
        if new_coupon and new_coupon.get('status'):
            fields_ = table_fields(Coupons)
            for f in fields_:
                if args.get(f):
                    setattr(new_coupon['obj'], f, args.get(f))
            return success_return(message=f"优惠券‘{name}’添加成功, ID: <{new_coupon['obj'].id}>")
        else:
            return false_return(message=f"优惠券‘{name}’已经存在")


@mall_ns.route('/coupons/<string:coupon_id>/take')
@mall_ns.param('coupon_id', 'Coupons 表中的ID')
@mall_ns.expect(head_parser)
class TakeCouponApi(Resource):
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.coupons.take_coupon")
    def post(self, **kwargs):
        """jkl90
        获取优惠券
        """
        coupon_id = kwargs.get('coupon_id')
        if not redis_db.exists(f"lock::coupon::{coupon_id}"):
            key = f"lock::coupon::{coupon_id}"
            redis_db.set(key, 1)
            redis_db.expire(key, 3)
            coupon_setting = Coupons.query.get(coupon_id)
            if coupon_setting:
                if coupon_setting.quota > 1:
                    take_coupon = new_data_obj("CouponReady", **{"coupon_id": coupon_id})
                    if take_coupon.get('status'):
                        coupon_setting.quota -= 1
                        coupon_setting.take_count += 1
                        # take_coupon['obj'].receiptor = kwargs['info']['user']
                    redis_db.delete(key)
                    return success_return() if take_coupon.get('status') else false_return(message=f"领取优惠券<{coupon_id}>失败")
                else:
                    redis_db.delete(key)
                    return false_return(message=f'优惠券<{coupon_id}>已领完')
            else:
                redis_db.delete(key)
                return false_return(message=f"未找到优惠券设置<{coupon_id}>")
        else:
            return false_return(message="优惠券正在发放，请稍后再试")
