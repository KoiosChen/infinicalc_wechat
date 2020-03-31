from flask import jsonify, request
from flask_restplus import Resource, fields, reqparse
from ..models import Users, Roles
from . import users
from app.auth import auths
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
import datetime
from ..decorators import permission_required
from ..swagger import return_dict, head_parser

users_ns = default_api.namespace('users', path='/users',
                                 description='包括注册、登陆、登出、获取用户信息、用户与角色操作等')

register_parser = reqparse.RequestParser()
register_parser.add_argument('username', required=True, help='用户名，非真名')
register_parser.add_argument('password', required=True, help='用户密码')
register_parser.add_argument('phone', required=True, help='用户注册用的手机')
register_parser.add_argument('email', required=True, help='用户注册用的邮箱')
register_parser.add_argument('role', required=True, help='用户角色')

login_parser = reqparse.RequestParser()
login_parser.add_argument('username', required=True,
                          help='可以是用户名、邮箱、手机号、微信ID等')
login_parser.add_argument('password', required=True,
                          help='当username传递的是手机号时，password对应为发送的验证码')
login_parser.add_argument('method', required=True, help='可以是password 或 code。 当username传递手机号时为code')
login_parser.add_argument('platform', required=True, help='平台字段吗， pc | mobile')

bind_role_parser = reqparse.RequestParser()
bind_role_parser.add_argument('user_id', location='json', help='可选，如果为空，则绑定发起请求的用户自身的角色（如果有权限）'
                                                               '如果修改他人权限，那么需把用户ID传递')
bind_role_parser.add_argument('role_id', required=True, type=list, location='json', help='选择的结果，role可多选，例如[1,2]')

return_json = users_ns.model('ReturnRegister', return_dict)


@users_ns.route('')
class QueryUsers(Resource):
    @users_ns.marshal_with(return_json)
    @permission_required("app.users.users_api.users_info")
    def get(self, info):
        """
        获取用户信息
        :return: json
        """
        user = info['user']
        return_user = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'login_time': info['login_info'].login_time
        }
        return success_return(return_user, "请求成功")

    @users_ns.doc(body=register_parser)
    @users_ns.marshal_with(return_json)
    def post(self):
        """
        用户注册
        """
        args = register_parser.parse_args()
        email = args['email']
        username = args['username']
        password = args['password']
        phone = args['phone']
        try:
            user = Users(email=email, username=username, password=password, phone=phone, status=1)
            db.session.add(user)
            if session_commit().get("code") == 'success':
                return_user = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'phone': user.phone
                }
                return success_return(return_user, "用户注册成功")
            else:
                return false_return({}, '用户注册失败')
        except Exception as e:
            logger.error(f"users::register::db_commit()::error --> {str(e)}")
            return false_return(data={}, message=str(e))


@users_ns.route('/login')
class Login(Resource):
    @users_ns.doc(body=login_parser)
    @users_ns.marshal_with(return_json)
    def post(self):
        """
        用户登陆，获取JWT
        """
        args = login_parser.parse_args()
        user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        username = args['username']
        password = args['password']
        method = args['method']
        platform = args['platform']
        return auths.authenticate(username, password, user_ip, platform, method=method)


@users_ns.route('/logout')
@users_ns.expect(head_parser)
class Logout(Resource):
    @users_ns.marshal_with(return_json)
    @permission_required("app.users.users_api.logout")
    def post(self, info):
        """
        用户登出
        """
        login_info = info.get('login_info')
        db.session.delete(login_info)
        result = success_return(message="登出成功") if session_commit().get("code") == 'success' else false_return(
            message='登出失败')
        return result


@users_ns.route('/<int:user_id>/roles')
@users_ns.expect(head_parser)
class UserRole(Resource):
    @users_ns.doc(body=bind_role_parser)
    @users_ns.marshal_with(return_json)
    @permission_required("app.users.users_api.bind_role")
    def post(self, **kwargs):
        """
        指定用户添加角色
        """
        args = bind_role_parser.parse_args()
        user = kwargs.get('user_id')
        old_roles = [r.name for r in user.roles]
        roles = args['role_id']
        to_add_roles = set(roles) - set(old_roles)
        to_delete_roles = set(old_roles) - set(roles)

        for roleid in to_add_roles:
            role_ = Roles.query.get(roleid)
            if not role_:
                return false_return(message=f'{roleid} is not exist')
            if role_ not in user.roles:
                user.roles.append(role_)

        for roleid in to_delete_roles:
            role_ = Roles.query.get(roleid)
            if not role_:
                return false_return(message=f'{roleid} is not exist')
            if role_ in user.roles:
                user.roles.remove(role_)
                
        return success_return(message='修改角色成功')
