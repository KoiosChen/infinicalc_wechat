from flask_restplus import Resource, reqparse
from app.models import Coupons, CouponReady
from app import redis_db, logger, coupon_lock
from app.common import success_return, false_return, session_commit
from app.decorators import permission_required
from app.swagger import head_parser
from .promotions_api import promotions_ns, return_json
from app.public_method import new_data_obj
import uuid
import threading
import json

consume_coupon_parser = reqparse.RequestParser()
consume_coupon_parser.add_argument('id', required=True, help='优惠券ID')
consume_coupon_parser.add_argument('quantity', required=True, help='优惠券消费数量')


def take_coupon(coupon_id, take_coupon_id, user, lock):
    if lock.acquire():
        try:
            coupon_setting = Coupons.query.get(coupon_id)
            if coupon_setting:
                if coupon_setting.quota > 0:
                    already_take = CouponReady.query.filter_by(coupon_id=coupon_id, consumer=user).all()
                    if len(already_take) >= coupon_setting.per_user:
                        raise AttributeError(f"此用户已领优惠券<{coupon_id}>达到最大数量")
                    new_coupon = new_data_obj("CouponReady", **{"id": take_coupon_id, "coupon_id": coupon_id})
                    if new_coupon.get('status'):
                        coupon_setting.quota -= 1
                        coupon_setting.take_count += 1
                        new_coupon['obj'].consumer = user
                        redis_db.set(f"new_coupon::{take_coupon_id}",
                                     json.dumps(success_return(message="领取成功")),
                                     ex=6000) \
                            if session_commit() else \
                            redis_db.set(f"new_coupon::{take_coupon_id}",
                                         json.dumps(false_return(message=f"领取优惠券<{coupon_id}>失败")),
                                         ex=6000)

                    else:
                        redis_db.set(f"new_coupon::{take_coupon_id}", json.dumps(false_return(message=f"领取失败")),
                                     ex=6000)
                else:
                    redis_db.set(f"new_coupon::{take_coupon_id}",
                                 json.dumps(false_return(message=f'优惠券<{coupon_id}>已领完')), ex=6000)
            else:
                redis_db.set(f"new_coupon::{take_coupon_id}",
                             json.dumps(false_return(message=f"未找到优惠券设置<{coupon_id}>")), ex=6000)
        except Exception as e:
            logger.error(f"领取优惠券失败，因为{e}")
            redis_db.set(f"new_coupon::{take_coupon_id}", json.dumps(false_return(message=f"{e}")), ex=6000)
        finally:
            lock.release()


@promotions_ns.route('/coupons/<string:coupon_id>/take')
@promotions_ns.param('coupon_id', 'Coupons 表中的ID')
@promotions_ns.expect(head_parser)
class TakeCouponApi(Resource):
    @promotions_ns.marshal_with(return_json)
    @permission_required("frontstage.app.promotions.coupons.take_coupon")
    def get(self, **kwargs):
        """
        获取优惠券
        """
        take_coupon_id = str(uuid.uuid4())
        user = kwargs['info']['user']
        coupon_thread = threading.Thread(target=take_coupon,
                                         args=(kwargs.get('coupon_id'), take_coupon_id, user.id, coupon_lock))
        coupon_thread.start()
        coupon_thread.join()
        k = f"new_coupon::{take_coupon_id}"
        if redis_db.exists(k):
            result = json.loads(redis_db.get(k))
            redis_db.delete(k)

            if result.get("code") == "success":
                return result
            else:
                return result, 400
