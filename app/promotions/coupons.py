from flask_restplus import Resource, reqparse
from app.models import Permission
from app.decorators import permission_required
from app.swagger import head_parser
from .promotions_api import promotions_ns, return_json
from app.public_method import query_coupon

consume_coupon_parser = reqparse.RequestParser()
consume_coupon_parser.add_argument('id', required=True, help='优惠券ID')
consume_coupon_parser.add_argument('quantity', required=True, help='优惠券消费数量')


@promotions_ns.route('/coupons/<string:coupon_id>/take')
@promotions_ns.param('coupon_id', 'Coupons 表中的ID')
@promotions_ns.expect(head_parser)
class TakeCouponApi(Resource):
    @promotions_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """
        获取优惠券
        """
        return query_coupon(**kwargs)
