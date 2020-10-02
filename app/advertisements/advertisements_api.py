from ..swagger import return_dict
from flask_restplus import Resource, reqparse
from .. import default_api, db
from ..common import success_return, false_return, submit_return, sort_by_order
from ..public_method import new_data_obj, get_table_data, get_table_data_by_id
from ..decorators import permission_required
from ..swagger import head_parser, page_parser
from ..models import Permission, Advertisements
from app.wechat.qqcos import QcloudCOS, delete_object
from collections import defaultdict
import datetime

ad_ns = default_api.namespace('Advertisements', path='/advertisements', description='广告位接口')

return_json = ad_ns.model('ReturnRegister', return_dict)

get_ad_by_position_parser = reqparse.RequestParser()
get_ad_by_position_parser.add_argument('position', required=True, help='位置标签名称')

add_ad_parser = reqparse.RequestParser()

change_ad_parser = reqparse.RequestParser()


@ad_ns.route('/<string:position>')
@ad_ns.param('position', '广告位标识名称')
@ad_ns.expect(head_parser)
class GetAdByPosition(Resource):
    @ad_ns.marshal_with(return_json)
    @ad_ns.doc(body=add_ad_parser)
    @permission_required([Permission.USER, "app.advertisements.advertisements_api.get_by_position"])
    def get(self, **kwargs):
        """
        获取对应位置的广告
        """
        args = defaultdict(dict)
        args['search']['position'] = kwargs['position']
        advance_search = [{"key": "start_at", "value": datetime.datetime.now(), "operator": "__le__"},
                          {"key": "end_at", "value": datetime.datetime.now(), "operator": "__ge__"},
                          {"key": "delete_at", "value": None, "operator": "__eq__"}]
        ad_result = get_table_data(Advertisements, args, appends=['ad_image'], removes=['image'],
                                   advance_search=advance_search)
        return success_return(ad_result['records'][0] if ad_result['records'] else {})
