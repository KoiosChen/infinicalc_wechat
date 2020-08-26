from ..swagger import return_dict
from flask_restplus import Resource, reqparse
from .. import default_api, db
from ..common import success_return, false_return, submit_return, sort_by_order
from ..public_method import new_data_obj, get_table_data, get_table_data_by_id
from ..decorators import permission_required
from ..swagger import head_parser, page_parser
from ..models import Banners, Permission, ObjStorage, NewsCenter
from app.wechat.qqcos import QcloudCOS, delete_object
import datetime

news_center_ns = default_api.namespace('NEWS CENTER', path='/news_center', description='资讯中心')

return_json = news_center_ns.model('ReturnRegister', return_dict)

add_news_parser = reqparse.RequestParser()
add_news_parser.add_argument('title', required=True, help='主标题')
add_news_parser.add_argument('sub_title', help='副标题')
add_news_parser.add_argument('cover_image', required=True, help='封面图片')
add_news_parser.add_argument('content', required=True, help='富文本内容')
add_news_parser.add_argument('news_section_id', required=True, help='归属栏目ID')
add_news_parser.add_argument('order', type=int, help='banner顺序，大于等于0的整数')

update_news_parser = add_news_parser.copy()

news_page_parser = page_parser.copy()
news_page_parser.add_argument("section_name", help='根据栏目名称查询')


@news_center_ns.route('')
@news_center_ns.expect(head_parser)
class NewsCenterApi(Resource):
    @news_center_ns.marshal_with(return_json)
    @news_center_ns.expect(news_page_parser)
    @permission_required([Permission.USER, "app.news_center.query_news"])
    def get(self, **kwargs):
        """
        获取资讯内容
        """
        args = news_page_parser.parse_args()
        args['search'] = {'delete_at': None}
        if args.get("section_name"):
            args['search']['section_name'] = args.get('section_name')
        news_result = get_table_data(NewsCenter, args, appends=['news_section', 'news_cover_image'],
                                     removes=['cover_image', 'news_section_id'])

        sort_by_order(news_result['records'])
        return success_return(news_result)

    @news_center_ns.doc(body=add_news_parser)
    @news_center_ns.marshal_with(return_json)
    @permission_required("app.news_center.add_news")
    def post(self, **kwargs):
        """新增资讯"""
        args = add_news_parser.parse_args()
        new_news = new_data_obj("NewsCenter", **args)
        if new_news:
            if new_news.get('status'):
                return submit_return(f"新增资讯成功<{new_news['obj'].id}>", "新增资讯失败")
            else:
                cos_client = QcloudCOS()
                cos_client.delete(ObjStorage.query.get(args['cover_image']).obj_key)
                return false_return(message=f"<{args['title']}>已经存在"), 400
        else:
            cos_client = QcloudCOS()
            cos_client.delete(ObjStorage.query.get(args['cover_image']).obj_key)
            return false_return(message="新增新闻失败"), 400


@news_center_ns.route('/<string:news_id>')
@news_center_ns.param('news_id', 'news_center id')
@news_center_ns.expect(head_parser)
class NewsCenterByIDApi(Resource):
    @news_center_ns.marshal_with(return_json)
    @permission_required([Permission.USER, "app.news.query_news_id"])
    def get(self, **kwargs):
        """
        获取指定新闻内容
        """
        return success_return(
            get_table_data_by_id(NewsCenter, kwargs['news_id'], appends=['news_cover_image', 'news_section'],
                                 removes=['cover_image', 'news_section_id']))

    @news_center_ns.doc(body=update_news_parser)
    @news_center_ns.marshal_with(return_json)
    @permission_required("app.news.update_news_by_id")
    def put(self, **kwargs):
        """更新新闻"""
        args = update_news_parser.parse_args()
        __news = NewsCenter.query.get(kwargs['news_id'])
        if __news:
            for k, v in args.items():
                if hasattr(__news, k) and v:
                    setattr(__news, k, v)
            return submit_return(f"资讯更新成功{args.keys()}", f"资讯更新失败{args.keys()}")
        else:
            return false_return(message=f"{kwargs['news_id']} 不存在")

    @news_center_ns.marshal_with(return_json)
    @permission_required("app.news_center.delete_news")
    def delete(self, **kwargs):
        """删除资讯"""
        news = NewsCenter.query.get(kwargs['news_id'])
        if news:
            news.delete_at = datetime.datetime.now()
            return submit_return("删除资讯成功", "删除资讯失败")
        else:
            return false_return(message=f"{kwargs['news_id']}不存在")
