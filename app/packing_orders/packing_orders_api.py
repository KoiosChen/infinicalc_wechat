from flask_restplus import Resource, reqparse
from ..models import PackingItemOrders, Permission, make_order_id, TotalCargoes, ShoppingCart
from .. import db, default_api, logger
from ..common import success_return, false_return, submit_return, session_commit
from ..public_method import get_table_data, get_table_data_by_id, new_data_obj
from ..decorators import permission_required
from ..swagger import return_dict, page_parser
import json
from decimal import Decimal

packing_ns = default_api.namespace('Packing Orders', path='/packing_orders', description='分装接口')

return_json = packing_ns.model('ReturnResult', return_dict)

packing_page_parser = page_parser.copy()
packing_page_parser.add_argument('Authorization', required=True, location='headers')

new_packing_order_parser = reqparse.RequestParser()
new_packing_order_parser.add_argument('Authorization', required=True, location='headers')


@packing_ns.route('/<string:cargo_id>')
@packing_ns.param('cargo_id', 'TotalCargoes ID')
class PackingAPI(Resource):
    @packing_ns.marshal_with(return_json)
    @packing_ns.expect(packing_page_parser)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """
        获取对应仓储货物分装order订单
        """
        try:
            cargo = TotalCargoes.query.get(kwargs['cargo_id'])
            if cargo.owner_id != kwargs['current_user'].id:
                raise Exception(f"货物{kwargs['cargo_id']}不属于当前用户{kwargs['current_user'].id}")

            args = packing_page_parser.parse_args()
            if 'search' not in args.keys():
                args['search'] = {}
            args['search']['total_cargoes_id'] = kwargs['cargo_id']
            packing_order = get_table_data(PackingItemOrders, args)
            # packing_order['max_packing'] = int(cargo.last_total * Decimal("0.5") / (Decimal("0.5") * Decimal("0.9255")))
            return success_return(packing_order, "请求成功")
        except Exception as e:
            return false_return(message=str(e)), 400

    @packing_ns.marshal_with(return_json)
    @packing_ns.expect(new_packing_order_parser)
    @permission_required(Permission.USER)
    def post(self, **kwargs):
        """
        对指定仓储货物产生一个预分装的订单号
        """
        try:
            cargo = TotalCargoes.query.get(kwargs['cargo_id'])
            max_packing = str(cargo.last_total * Decimal('0.5') // (Decimal('0.5') * Decimal('0.9255')))
            if not cargo or cargo.delete_at or cargo.last_total <= 0.00:
                raise Exception(f"货物{kwargs['cargo_id']}不存在或已经分装完")

            if not cargo.owner_id == kwargs['current_user'].id:
                raise Exception(f"货物{kwargs['cargo_id']}不属于当前用户{kwargs['current_user'].id}")

            exist_packing_order = PackingItemOrders.query.filter(PackingItemOrders.shop_order_id.__eq__(None),
                                                                 PackingItemOrders.packing_at.__eq__(None)).all()
            for o in exist_packing_order:
                exist_shopping_cart = ShoppingCart.query.filter(ShoppingCart.packing_item_order.__eq__(o.id)).all()
                for so in exist_shopping_cart:
                    db.session.delete(so)
                db.session.delete(o)
            db.session.commit()

            new_packing_order_id = make_order_id()
            new_packing_order = new_data_obj('PackingItemOrders',
                                             **{'id': new_packing_order_id, 'total_cargoes_id': kwargs['cargo_id']})

            if new_packing_order and new_packing_order.get('status'):
                commit_result = session_commit()
                if commit_result.get("code") == 'success':
                    return success_return(data={'id': new_packing_order['obj'].id, 'max_packing': max_packing})
                else:
                    raise Exception(json.dumps(commit_result))
            else:
                raise Exception("无法生成预订单")

        except Exception as e:
            return false_return(message=str(e)), 400
