from flask_restplus import Resource, reqparse
from ..models import PromotionGroups, Promotions, Coupons, CouponReady, Benefits
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id
from ..decorators import permission_required
from ..swagger import return_dict, head_parser
from app.type_validation import checkout_sku_type

orders_ns = default_api.namespace('orders', path='/orders', description='下单相关API')

return_json = orders_ns.model('ReturnRegister', return_dict)

checkout_parser = reqparse.RequestParser()
checkout_parser.add_argument('sku', required=True, type=checkout_sku_type,
                             help="""传递数组，其中的元素为json：{'id': {'required': True, 'type': str},
                                    'quantity': {'required': True, 'type': int}}""",
                             location='json')
checkout_parser.add_argument('desc', help='促销活动描述')
checkout_parser.add_argument('group_id', required=True,
                             help='组ID， 0 为特殊组，特殊组和任何组不互斥。group_id 为-1表示是发优惠券，>=0的group，为活动')
checkout_parser.add_argument('priority', required=True, help='1-10, 10优先级最低，当有组互斥时，使用优先级最高的，0优先级最高')
