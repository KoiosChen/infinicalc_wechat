from flask_restplus import Resource, reqparse
from ..models import ObjStorage, Permission
from .. import logger
from ..common import success_return, false_return, session_commit
from ..public_method import new_data_obj, get_table_data
from ..decorators import permission_required
from ..swagger import head_parser, return_dict, page_parser
from werkzeug.datastructures import FileStorage
from .. import default_api
from app.wechat.qqcos import QcloudCOS
import uuid
from ..type_validation import upload_file_type

cos_ns = default_api.namespace('object_storage', path='/object_storage',
                               description='图片文件')

return_json = cos_ns.model('ReturnRegister', return_dict)

upload_parser = reqparse.RequestParser()
upload_parser.add_argument('prefix', type=str)
upload_parser.add_argument('obj_type', type=int, choices=[0, 1, 2], help='0 图片 1 视频 2 文本')
upload_parser.add_argument('file', required=True, type=FileStorage, location='files')


@cos_ns.route('')
@cos_ns.expect(head_parser)
class ObjectStorageApi(Resource):
    @cos_ns.marshal_with(return_json)
    @cos_ns.doc(body=page_parser)
    @permission_required("app.img_urls.img_url.query_img_urls")
    def get(self, **kwargs):
        """
        获取所有图片
        """
        args = page_parser.parse_args()
        return success_return(get_table_data(ObjStorage, args))

    @cos_ns.doc(body=upload_parser)
    @cos_ns.marshal_with(return_json)
    @permission_required(["app.img_urls.img_url.upload_img", Permission.USER])
    def post(self, **kwargs):
        """上传对象"""
        args = upload_parser.parse_args()
        logger.debug(f"upload object to storage {args}")
        upload_object = args['file']
        logger.debug(upload_object)
        cos_client = QcloudCOS()
        if upload_file_type(args['obj_type'], upload_object.mimetype):
            ext_name = upload_object.filename.split('.')[-1]
            object_key = 'banners/' + str(uuid.uuid4()) + '.' + ext_name
            store_result = cos_client.upload(object_key, upload_object.read())
            store_result['obj_type'] = args['obj_type']
            logger.debug(store_result)
            if store_result.get("code") == "success":
                new_object = new_data_obj("ObjStorage", **store_result.get("data"))
                if session_commit().get('code') == 'success':
                    return success_return(
                        data={'object_id': new_object['obj'].id, 'path': store_result['data']['url']})
                else:
                    cos_client.delete(store_result['obj_key'])
                    return false_return(message=f"上传对象失败")
            else:
                return false_return(message="cos上传失败"), 400
        else:
            return false_return(message="上传文件格式与选择类型不匹配"), 400
