from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import new_data_obj, get_table_data
from .promotions_api import promotions_ns, return_json
from app.swagger import head_parser, page_parser
from ..decorators import permission_required
from flask_restplus import Resource, reqparse
from ..models import FranchiseeGroupPurchase, Permission, SKU

get_order_parser = page_parser.copy()

new_order_parser = reqparse.RequestParser()
new_order_parser.add_argument("id", required=True, type=str, help='团购ID')


@promotions_ns.route('')
@promotions_ns.expect(head_parser)
class GetFranchiseeGroupPurchase(Resource):
    @promotions_ns.marshal_with(return_json)
    @promotions_ns.doc(body=get_order_parser)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """
        查询所有可用的团购活动
        """
        args = get_order_parser.parse_args()
        args['search'] = dict()
        args['search']['status'] = 1
        args['search']['delete_at'] = None
        return success_return(get_table_data(FranchiseeGroupPurchase, args, appends=['sku']), "请求成功")


@promotions_ns.route('/<string:gp_id>')
@promotions_ns.expect(head_parser)
class NewFranchiseeGroupPurchaseOrder(Resource):
    @promotions_ns.marshal_with(return_json)
    @promotions_ns.doc(body=new_order_parser)
    @permission_required(Permission.USER)
    def post(self, **kwargs):
        args = new_order_parser.parse_args()
        current_user = kwargs.get('current_user')
        gp_obj = FranchiseeGroupPurchase.query.get(kwargs['gp_id'])
        sku_id = gp_obj.sku_id
        sku = SKU.query.get(sku_id)
        if sku and sku.status == 1 and sku.delete_at is None:
            cart_item = new_data_obj("ShoppingCart",
                                     **{"customer_id": current_user.id, "sku_id": sku_id, "delete_at": None,
                                        "fgp_id": kwargs['gp_id']})

            if cart_item:
                if cart_item['status']:
                    cart_item['obj'].quantity = gp_obj.amount
                else:
                    cart_item['obj'].quantity += gp_obj.amount

                return submit_return(f"购物车添加成功<{cart_item['obj'].id}>", "购物出添加失败")
            else:
                return false_return(message=f"将<{sku_id}>添加规到购物车失败"), 400
        else:
            return false_return(message=f"<{sku_id}>已下架"), 400
