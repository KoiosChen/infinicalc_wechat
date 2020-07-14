from ..swagger import return_dict
from flask_restplus import Resource, reqparse
from .. import default_api, logger, db
from ..common import success_return, false_return, submit_return
from ..public_method import new_data_obj, get_table_data, table_fields, get_table_data_by_id
from ..decorators import permission_required
from ..swagger import head_parser, page_parser
from ..models import Banners
from werkzeug.datastructures import FileStorage
from ..obj_storage.qqcos import QcloudCOS
from ..type_validation import upload_file_type
import uuid
import datetime

banner_ns = default_api.namespace('banners', path='/banners', description='首页Banner')

return_json = banner_ns.model('ReturnRegister', return_dict)

add_banner_parser = reqparse.RequestParser()
add_banner_parser.add_argument('name', required=True, help='Banner名称')
add_banner_parser.add_argument('object', required=True, type=FileStorage, help='上传对象', location='files')
add_banner_parser.add_argument('type', required=True, type=int, choices=[0, 1, 2], help='0 图片 1 视频 2 文本', default=0)
add_banner_parser.add_argument('order', type=int, help='banner顺序，大于等于0的整数')
add_banner_parser.add_argument('url', help='点击跳转的URL，空值表示不可点击')

update_banner_parser = add_banner_parser.copy()
update_banner_parser.replace_argument('name', required=False, help='Banner名称')
update_banner_parser.replace_argument('object', required=False, type=FileStorage, help='上传对象', location='files')
update_banner_parser.replace_argument('type', required=False, type=int, choices=[0, 1, 2], help='0 图片 1 视频 2 文本',
                                      default=0)


def banner_object_upload(upload_object, **args):
    cos_client = QcloudCOS()
    if upload_file_type(args['type'], upload_object.mimetype):
        ext_name = upload_object.filename.split('.')[-1]
        object_key = 'banners/' + str(uuid.uuid4()) + '.' + ext_name
        store_result = cos_client.upload(object_key, upload_object.stream)
        store_result['obj_type'] = args['type']
        logger.debug(store_result)
        if store_result.get("code") == "success":
            new_object = new_data_obj("ObjStorage", **store_result.get("data"))
            if not args.get('new_banner'):
                new_banner = new_data_obj("Banners", **{"name": args['name'], "order": args['order']})
            else:
                now_banner = args.get('new_banner')
                new_banner = {"obj": now_banner, "status": True}
                if now_banner.banner_contents:
                    cos_client.delete(now_banner.banner_contents.obj_key)
                    db.session.delete(now_banner.banner_contents)
                    db.session.flush()

            if new_object and new_banner and new_banner.get('status') and new_banner.get('status'):
                new_banner['obj'].objects = new_object['obj'].id
                return submit_return("新增banner成功", "新增banner失败")
            else:
                logger.error(f">>> {new_banner} {new_object}")
                cos_client.delete(object_key)
                return false_return(f"新增banner失败")
        else:
            return false_return(message="COS上传对象失败"), 400
    else:
        return false_return(message="上传文件格式和所选格式不同"), 400


@banner_ns.route('')
@banner_ns.expect(head_parser)
class BannersApi(Resource):
    @banner_ns.marshal_with(return_json)
    @banner_ns.doc(body=page_parser)
    @permission_required("app.banners.query_banners")
    def get(self, **kwargs):
        """
        获取全部Banner
        """
        args = page_parser.parse_args()
        return success_return(get_table_data(Banners, args, appends=['banner_contents']))

    @banner_ns.doc(body=add_banner_parser)
    @banner_ns.marshal_with(return_json)
    @permission_required("app.mall.banners.add_banner")
    def post(self, **kwargs):
        """新增Banner"""
        args = add_banner_parser.parse_args()
        upload_object = args['object']
        banner_db = Banners.query.filter_by(name=args['name']).first()
        if banner_db:
            return false_return(message=f"<{args['name']}>已经存在"), 400

        logger.debug(upload_object.mimetype)
        return banner_object_upload(upload_object, **args)


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
        return success_return(get_table_data_by_id(Banners, kwargs['banner_id']))

    @banner_ns.doc(body=update_banner_parser)
    @banner_ns.marshal_with(return_json)
    @permission_required("app.mall.banners.update_banner")
    def put(self, **kwargs):
        """更新banner"""
        args = update_banner_parser.parse_args()
        __banner = Banners.query.get(kwargs['banner_id'])
        args['new_banner'] = __banner
        if __banner:
            for k, v in args.items():
                if k == 'type' and args.get('type') and not args.get('object'):
                    return false_return('文件类型不可单独修改')
                elif k == 'object' and args.get('object'):

                    update_objects_result = banner_object_upload(args['object'], **args)
                    if update_objects_result.get('code') == 'false':
                        return update_objects_result
                else:
                    if hasattr(__banner, k) and v:
                        setattr(__banner, k, v)
            return submit_return(f"banner更新成功{args.keys()}", f"banner更新失败{args.keys()}")
        else:
            return false_return(message=f"{kwargs['banner_id']} 不存在")

    @banner_ns.marshal_with(return_json)
    @permission_required("app.mall.banners.delete_banner")
    def delete(self, **kwargs):
        """删除品牌"""
        brand = Banners.query.get(kwargs['banner_id'])
        if brand:
            if brand.banner_contents:
                brand_objs = brand.banner_contents
                cos_client = QcloudCOS()
                try:
                    cos_client.delete(brand_objs.obj_key)
                except Exception as e:
                    return false_return(message=f"删除cos中图片失败，删除Banner {kwargs['banner_id']}失败")
                db.session.delete(brand_objs)
                db.session.delete(brand)
            else:
                db.session.delete(brand)
            return submit_return("删除banner成功", "删除banner失败")
        else:
            return false_return(message=f"{kwargs['banner_id']}不存在")
