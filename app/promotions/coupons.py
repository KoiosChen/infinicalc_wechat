from flask_restplus import Resource, fields, reqparse
from app.models import Users, Coupons
from app import db, redis_db, logger
from app.common import success_return, false_return, session_commit
import datetime
from app.decorators import permission_required
from app.swagger import return_dict, head_parser
from .promotions_api import promotions_ns, return_json
from app.public_method import get_table_data, new_data_obj, table_fields
import uuid

consume_coupon_parser = reqparse.RequestParser()
consume_coupon_parser.add_argument('id', required=True, help='优惠券ID')
consume_coupon_parser.add_argument('quantity', required=True, help='优惠券消费数量')


@promotions_ns.route('/coupons/<string:coupon_id>/take')
@promotions_ns.param('coupon_id', 'Coupons 表中的ID')
# @promotions_ns.expect(head_parser)
class TakeCouponApi(Resource):
    @promotions_ns.marshal_with(return_json)
    # @permission_required("frontstage.app.mall.coupons.take_coupon")
    def post(self, **kwargs):
        """
        获取优惠券
        """
        coupon_id = kwargs.get('coupon_id')
        if not redis_db.exists(f"lock::coupon::{coupon_id}"):
            key = f"lock::coupon::{coupon_id}"
            redis_db.set(key, 1)
            redis_db.expire(key, 3)
            coupon_setting = Coupons.query.get(coupon_id)
            if coupon_setting:
                if coupon_setting.quota > 0:
                    take_coupon = new_data_obj("CouponReady", **{"id": str(uuid.uuid4()), "coupon_id": coupon_id})
                    if take_coupon.get('status'):
                        coupon_setting.quota -= 1
                        coupon_setting.take_count += 1
                        # take_coupon['obj'].consumer = kwargs['info']['user']
                        redis_db.delete(key)
                        return success_return(message="领取成功") if session_commit() else false_return(
                            message=f"领取优惠券<{coupon_id}>失败"), 400
                    else:
                        return false_return(message=f"领取失败"), 400
                else:
                    redis_db.delete(key)
                    return false_return(message=f'优惠券<{coupon_id}>已领完'), 400
            else:
                redis_db.delete(key)
                return false_return(message=f"未找到优惠券设置<{coupon_id}>"), 400
        else:
            return false_return(message="优惠券正在发放，请稍后再试"), 400
