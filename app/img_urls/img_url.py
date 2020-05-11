from flask_restplus import Resource, reqparse
from ..models import ImgUrl
from .. import logger, fastdfs_client
from ..common import success_return, false_return
from ..public_method import new_data_obj, get_table_data
from ..decorators import permission_required
from ..swagger import head_parser, return_dict, page_parser
from werkzeug.datastructures import FileStorage
from .. import default_api

img_ns = default_api.namespace('img_urls', path='/img_urls',
                               description='图片文件')

return_json = img_ns.model('ReturnRegister', return_dict)

upload_img_parser = reqparse.RequestParser()
upload_img_parser.add_argument('file', required=True, type=FileStorage, location='files')


@img_ns.route('')
@img_ns.expect(head_parser)
class ImageApi(Resource):
    @img_ns.marshal_with(return_json)
    @img_ns.doc(body=page_parser)
    @permission_required("app.img_urls.img_url.query_img_urls")
    def get(self, **kwargs):
        """
        获取所有图片
        """
        args = page_parser.parse_args()
        return success_return(get_table_data(ImgUrl, args['page'], args['current'], args['size']), "")

    @img_ns.doc(body=upload_img_parser)
    @img_ns.marshal_with(return_json)
    @permission_required("app.img_urls.img_url.upload_img")
    def post(self, **kwargs):
        """上传图片"""
        args = upload_img_parser.parse_args()
        logo_file = args['file']
        if 'image' in logo_file.mimetype:
            ext_name = logo_file.filename.split('.')[-1]
            store_result = fastdfs_client.upload_by_buffer(args['file'].read(), file_ext_name=ext_name)
            logger.debug(store_result)
            if store_result.get("Status") == "Upload successed.":
                new_logo = new_data_obj("ImgUrl", **{"path": store_result['Remote file_id'].decode(), "attribute": 5})
                return success_return(
                    data={'img_id': new_logo['obj'].id, 'path': store_result['Remote file_id'].decode()})
            else:
                return false_return(message="fastdfs上传失败"), 400
        else:
            return false_return(message="上传文件格式是图片"), 400
