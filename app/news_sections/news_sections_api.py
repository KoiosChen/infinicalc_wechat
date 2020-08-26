from ..swagger import return_dict
from flask_restplus import Resource, reqparse
from .. import default_api, db
from ..common import success_return, false_return, submit_return, sort_by_order
from ..public_method import new_data_obj, get_table_data, get_table_data_by_id
from ..decorators import permission_required
from ..swagger import head_parser, page_parser
from ..models import Banners, Permission, ObjStorage, NewsSections
from app.wechat.qqcos import QcloudCOS, delete_object
import datetime

news_section_ns = default_api.namespace('NEWS SECTION', path='/news_sections', description='资讯栏目')

return_json = news_section_ns.model('ReturnRegister', return_dict)

add_section_parser = reqparse.RequestParser()
add_section_parser.add_argument('name', required=True, help='栏目名称')
add_section_parser.add_argument('section_image', help='栏目图标')
add_section_parser.add_argument('order', type=int, help='banner顺序，大于等于0的整数')

update_section_parser = add_section_parser.copy()

section_page_parser = page_parser.copy()


@news_section_ns.route('')
@news_section_ns.expect(head_parser)
class NewsSectionApi(Resource):
    @news_section_ns.marshal_with(return_json)
    @news_section_ns.expect(section_page_parser)
    @permission_required([Permission.USER, "app.news_sections.query_sections"])
    def get(self, **kwargs):
        """
        获取栏目
        """
        args = section_page_parser.parse_args()
        args['search'] = {'delete_at': None}
        section_result = get_table_data(NewsSections, args, appends=['section_image'])
        sort_by_order(section_result['records'])
        return success_return(section_result)

    @news_section_ns.doc(body=add_section_parser)
    @news_section_ns.marshal_with(return_json)
    @permission_required("app.news_sections.add_section")
    def post(self, **kwargs):
        """新增栏目"""
        args = add_section_parser.parse_args()
        new_section = new_data_obj("NewsSections", **args)
        if new_section:
            if new_section.get('status'):
                return submit_return(f"新增栏目成功<{new_section['obj'].id}>", "新增栏目失败")
            else:
                cos_client = QcloudCOS()
                cos_client.delete(ObjStorage.query.get(args['section_image']).obj_key)
                return false_return(message=f"<{args['name']}>已经存在"), 400
        else:
            cos_client = QcloudCOS()
            cos_client.delete(ObjStorage.query.get(args['section_image']).obj_key)
            return false_return(message="新增栏目失败"), 400


@news_section_ns.route('/<string:section_id>')
@news_section_ns.param('section_id', 'news_sections id')
@news_section_ns.expect(head_parser)
class NewsSectionsByID(Resource):
    @news_section_ns.doc(body=update_section_parser)
    @news_section_ns.marshal_with(return_json)
    @permission_required("app.news.update_news_by_id")
    def put(self, **kwargs):
        """更新栏目"""
        args = update_section_parser.parse_args()
        __news = NewsSections.query.get(kwargs['section_id'])
        if __news:
            for k, v in args.items():
                if hasattr(__news, k) and v:
                    setattr(__news, k, v)
            return submit_return(f"栏目更新成功{args.keys()}", f"栏目更新失败{args.keys()}")
        else:
            return false_return(message=f"{kwargs['section_id']} 不存在")

    @news_section_ns.marshal_with(return_json)
    @permission_required("app.news_center.delete_news")
    def delete(self, **kwargs):
        """删除栏目"""
        section = NewsSections.query.get(kwargs['section_id'])
        if section and not section.news.all():
            section.delete_at = datetime.datetime.now()
            return submit_return("删除栏目成功", "删除栏目失败")
        else:
            return false_return(message=f"{kwargs['section_id']}不存在或有关联")


@news_section_ns.route('/<string:section_name>')
@news_section_ns.param('section_name', '栏目名称')
@news_section_ns.expect(head_parser)
class NewsSectionsByName(Resource):
    @news_section_ns.doc(body=update_section_parser)
    @news_section_ns.marshal_with(return_json)
    @permission_required("app.news_sections.get_id_by_name")
    def get(self, **kwargs):
        return success_return(data=NewsSections.query.filter_by(name=kwargs['section_name']).first().id)
