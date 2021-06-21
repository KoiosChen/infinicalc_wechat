from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import new_data_obj, get_table_data
from .promotions_api import promotions_ns, return_json
from app.swagger import head_parser, page_parser
from ..decorators import permission_required
from flask_restplus import Resource, reqparse
from ..models import FranchiseeGroupPurchase, Permission, SKU
from app.scene_invitation.scene_invitation_api import generate_code
from app import redis_db
import json

get_order_parser = page_parser.copy()

new_order_parser = reqparse.RequestParser()
new_order_parser.add_argument("id", required=True, type=str, help='团购ID')


@promotions_ns.route('/fgp')
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


@promotions_ns.route('/fgp/<string:gp_id>')
@promotions_ns.expect(head_parser)
class NewFranchiseeGroupPurchaseOrder(Resource):
    @promotions_ns.marshal_with(return_json)
    @promotions_ns.doc(body=get_order_parser)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """
        传入团购活动的id， /fgp get方法中获取
        """
        scene_invitation = generate_code(12)
        json_str = json.dumps({'gp_id': kwargs['gp_id'], 'salesman_id': kwargs['current_user'].id})
        redis_db.set(scene_invitation, json_str)
        redis_db.expire(scene_invitation, 86400)
        return success_return(data={'scene': "new_fgp", 'scene_invitation': scene_invitation})