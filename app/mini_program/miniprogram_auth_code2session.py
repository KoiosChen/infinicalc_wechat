import requests
from flask import request
from flask_restplus import Resource, reqparse
from app.models import Roles, Customers
from app.customers import customers
from app.frontstage_auth import auths
from app import db, default_api
from app.common import success_return, false_return, session_commit
from app.public_method import table_fields, get_table_data
import datetime
from app.decorators import permission_required
from app.swagger import return_dict, head_parser, page_parser
from app.public_user_func import register, modify_user_profile

app_id = "wxbd90eb9673088c7b"
app_secret = "3aa0c3296b1ee4ef09bf9f3c0a43b7ff"

mp_ns = default_api.namespace('mini_program', path='/mini_program', description='微信小程序交互相关接口')

return_json = mp_ns.model('ReturnRegister', return_dict)


@mp_ns.route('/<string:js_code>')
@mp_ns.param("js_code", "前端获取的临时code")
class MiniProgramAPI(Resource):
    @mp_ns.marshal_with(return_json)
    @permission_required("frontstage.app.mini_program.code2session.users_info")
    @mp_ns.expect(page_parser)
    def get(self, **kwargs):
        """
        使用code2session 获取用户openid, session_key
        """
        url = "https://api.weixin.qq.com/sns/jscode2session"
        params = {"appid": app_id, "secret": app_secret, "js_code": kwargs['js_code'],
                  "grant_type": "authorization_code"}
        r = requests.get(url, params=params)
        response = r.json()
        if response.get('errcode') == 0:
            return success_return(response, "请求成功")
        else:
            return false_return(response, "请求失败")
