from flask import jsonify, request
from flask_restplus import Resource, fields, reqparse
from ..models import Users, Roles, Menu, Permissions, role_menu
from . import sms
from app.auth import auths
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
import datetime
from ..decorators import permission_required
from ..swagger import return_dict, head_parser
from ..menus.menus_api import get_menus
from .send_sms import send_verification_code

sms_ns = default_api.namespace('sms', path='/sms', description='短信API接口')

sms_add_parser = reqparse.RequestParser()
sms_add_parser.add_argument('phone', required=True, help='手机号码，国内号')
sms_add_parser.add_argument('stage', required=True, help='front | back')

return_json = sms_ns.model('ReturnRegister', return_dict)


@sms_ns.route('')
class SendSMS(Resource):
    @sms_ns.doc(body=sms_add_parser)
    @sms_ns.marshal_with(return_json)
    def post(self, **kwargs):
        """
        发送短信
        """
        args = sms_add_parser.parse_args()
        return send_verification_code(phone=args['phone'], stage=args['stage'])
