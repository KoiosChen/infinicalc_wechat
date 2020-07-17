from ..swagger import return_dict
from flask_restplus import Resource, reqparse
from .. import default_api, db
from ..common import success_return, false_return, submit_return, sort_by_order
from ..public_method import new_data_obj, get_table_data, get_table_data_by_id
from ..decorators import permission_required
from ..swagger import head_parser, page_parser
from ..models import Banners, Permission, ObjStorage
from app.wechat.qqcos import QcloudCOS, delete_object

banner_ns = default_api.namespace('banners', path='/banners', description='首页Banner')

return_json = banner_ns.model('ReturnRegister', return_dict)

add_banner_parser = reqparse.RequestParser()
add_banner_parser.add_argument('name', required=True, help='Banner名称')
add_banner_parser.add_argument('object', required=True, type=str, help='上传对象')
add_banner_parser.add_argument('order', type=int, help='banner顺序，大于等于0的整数')
add_banner_parser.add_argument('url', help='点击跳转的URL，空值表示不可点击')

update_banner_parser = add_banner_parser.copy()
update_banner_parser.replace_argument('name', required=False, help='Banner名称')
update_banner_parser.replace_argument('object', required=False, type=str, help='上传对象')


@banner_ns.route('')
@banner_ns.expect(head_parser)
class BannersApi(Resource):
    @banner_ns.marshal_with(return_json)
    @banner_ns.doc(body=page_parser)
    @permission_required([Permission.USER, "app.banners.query_banners"])
    def get(self, **kwargs):
        """
        获取全部Banner
        """
        args = page_parser.parse_args()
        banner_result = get_table_data(Banners, args, appends=['banner_contents'], removes=['objects'])
        sort_by_order(banner_result['records'])
        return success_return(banner_result)

    @banner_ns.doc(body=add_banner_parser)
    @banner_ns.marshal_with(return_json)
    @permission_required("app.mall.banners.add_banner")
    def post(self, **kwargs):
        """新增Banner"""
        args = add_banner_parser.parse_args()
        new_banner = new_data_obj("Banners",
                                  **{"name": args['name'], "order": args['order'], "objects": args['object']})
        if new_banner:
            if new_banner.get('status'):
                return submit_return("新增banner成功", "新增banner失败")
            else:
                cos_client = QcloudCOS()
                cos_client.delete(ObjStorage.query.get(args['object']).obj_key)
                return false_return(message=f"<{args['name']}>已经存在"), 400
        else:
            cos_client = QcloudCOS()
            cos_client.delete(ObjStorage.query.get(args['object']).obj_key)
            return false_return(message="新增banner失败"), 400


@banner_ns.route('/<string:banner_id>')
@banner_ns.param('banner_id', 'banner id')
@banner_ns.expect(head_parser)
class BannerApi(Resource):
    @banner_ns.marshal_with(return_json)
    @permission_required("app.mall.banners.query_banner")
    def get(self, **kwargs):
        """
        获取指定品牌数据
        """
        return success_return(get_table_data_by_id(Banners, kwargs['banner_id'],appends=['banner_contents']))

    @banner_ns.doc(body=update_banner_parser)
    @banner_ns.marshal_with(return_json)
    @permission_required("app.mall.banners.update_banner")
    def put(self, **kwargs):
        """更新banner"""
        args = update_banner_parser.parse_args()
        __banner = Banners.query.get(kwargs['banner_id'])
        if __banner:
            for k, v in args.items():
                if hasattr(__banner, k) and v:
                    setattr(__banner, k, v)
            return submit_return(f"banner更新成功{args.keys()}", f"banner更新失败{args.keys()}")
        else:
            return false_return(message=f"{kwargs['banner_id']} 不存在")

    @banner_ns.marshal_with(return_json)
    @permission_required("app.mall.banners.delete_banner")
    def delete(self, **kwargs):
        """删除Banner"""
        brand = Banners.query.get(kwargs['banner_id'])
        if brand:
            if brand.banner_contents:
                brand_objs = brand.banner_contents
                result = delete_object(brand_objs)
                if result.get('code') != 'success':
                    return result
            db.session.delete(brand)
            return submit_return("删除banner成功", "删除banner失败")
        else:
            return false_return(message=f"{kwargs['banner_id']}不存在")
