from flask import request
from flask_restplus import Resource, reqparse
from ..models import Users, Roles
from . import users
from app.auth import auths
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
from ..public_method import table_fields
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
from ..public_method import new_data_obj, get_table_data

users_ns = default_api.namespace('users', path='/users',
                                 description='包括注册、登陆、登出、获取用户信息、用户与角色操作等')

register_parser = reqparse.RequestParser()
register_parser.add_argument('phone', required=True, help='用户注册用的手机', location='json')
register_parser.add_argument('verify_code', required=True, help='验证码', location='json')
register_parser.add_argument('username', help='用户名，非真名，选填', location='json')
register_parser.add_argument('password', help='用户密码，选填', location='json')
register_parser.add_argument('email', help='用户注册用的邮箱，选填', location='json')
register_parser.add_argument('role_id', help='用户角色, 可多个，用list来传递', location='json', type=list)

login_parser = reqparse.RequestParser()
login_parser.add_argument('username', required=True, help='可以是用户名、邮箱、手机号、微信ID等')
login_parser.add_argument('password', required=True, help='当username传递的是手机号时，password对应为发送的验证码')
login_parser.add_argument('method', required=True, help='可以是password 或 code。 当username传递手机号时为code')
login_parser.add_argument('platform', required=True, help='平台字段吗， pc | mobile')

bind_role_parser = reqparse.RequestParser()
bind_role_parser.add_argument('role_id', required=True, type=list, location='json', help='选择的结果，role可多选，例如[1,2]')

update_user_parser = reqparse.RequestParser()
update_user_parser.add_argument('phone', help='用户手机号，如需更改，需要发送验证码认证，调用<string:phone>/verify_code 验证', location='json')
update_user_parser.add_argument('username', help='登陆用户名', location='json')
update_user_parser.add_argument('email', help='email', location='json')
update_user_parser.add_argument('true_name', help='真实姓名', location='json')
update_user_parser.add_argument('gender', help='性别 0:unknown 1:male, 2:female', location='json')
update_user_parser.add_argument('password', help='密码', location='json')
update_user_parser.add_argument('role_id', type=list, location='json', help='选择的结果，role可多选，例如[1,2]')
update_user_parser.add_argument('address', location='json', help='用户地址')

return_json = users_ns.model('ReturnRegister', return_dict)

page_parser.add_argument('Authorization', required=True, location='headers')


@users_ns.route('')
class QueryUsers(Resource):
    @users_ns.marshal_with(return_json)
    @permission_required("app.users.users_api.users_info")
    @users_ns.expect(page_parser)
    def get(self, info):
        """
        获取后端用户信息
        """
        args = page_parser.parse_args()
        return success_return(
            get_table_data(Users, args['page'], args['current'], args['size'], ['role'], ['password_hash']), "请求成功")

    @users_ns.doc(body=register_parser)
    @users_ns.marshal_with(return_json)
    def post(self):
        """
        后端用户注册
        """
        args = register_parser.parse_args()
        phone = args['phone']
        username = args.get('username')
        password = args.get('password')
        email = args.get('email')
        verify_code = args['verify_code']
        role_ids = args.get('role_id')
        key = f'back::verification_code::{phone}'
        try:
            if redis_db.exists(key) and redis_db.get(key) == verify_code:
                new_user = new_data_obj('Users', **{"phone": phone, "status": 1})
                if new_user and new_user.get('status'):
                    user = new_user['obj']
                    if username:
                        user.username = username
                    if password:
                        user.password = password
                    if email:
                        user.email = email
                else:
                    return false_return(message=f"<{phone}>已经存在"), 400

                if not role_ids:
                    role_ids = list()
                    role_ids.append(new_data_obj("Roles", **{"name": "normal_user"})['obj'].id)

                for id_ in role_ids:
                    user.roles.append(Roles.query.get(id_))
                db.session.add(user)
                if session_commit().get("code") == 'success':
                    return_user = {
                        'id': user.id,
                        'phone': user.phone
                    }
                    return success_return(return_user, "用户注册成功")
                else:
                    return false_return({}, '用户注册失败'), 400
            else:
                return false_return(message='验证码错误'), 400
        except Exception as e:
            logger.error(f"customers::register::db_commit()::error --> {str(e)}")
            db.session.rollback()
            return false_return(data={}, message=str(e)), 400

    @users_ns.doc(body=update_user_parser)
    @users_ns.marshal_with(return_json)
    @permission_required("app.users.users_api.update_user_attributes")
    def put(self, **kwargs):
        """
        修改用户属性
        """
        args = update_user_parser.parse_args()
        user = kwargs['info']['user']
        fields_ = table_fields(Users, appends=['role_id'])
        for f in fields_:
            if f == 'role_id' and args.get(f):
                user.roles = []
                for r in args.get(f):
                    role = Roles.query.get(r)
                    user.roles.append(role)
            elif args.get(f):
                setattr(user, f, args.get(f))
        return success_return(message="更新成功")


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
class Logout(Resource):
    @users_ns.marshal_with(return_json)
    @permission_required("app.users.users_api.logout")
    @users_ns.expect(head_parser)
    def post(self, info):
        """
        用户登出
        """
        login_info = info.get('login_info')
        db.session.delete(login_info)
        result = success_return(message="登出成功") if session_commit().get("code") == 'success' else false_return(
            message='登出失败'), 400
        return result


@users_ns.route('/<string:user_id>/roles')
@users_ns.expect(head_parser)
@users_ns.param("user_id", "后台用户ID")
class UserRole(Resource):
    @permission_required("app.users.users_api.bind_role")
    @users_ns.doc(body=bind_role_parser)
    @users_ns.marshal_with(return_json)
    def post(self, **kwargs):
        """
        指定用户添加角色
        """
        args = bind_role_parser.parse_args()
        user = Users.query.get(kwargs.get('user_id'))
        if not user:
            return false_return(message='用户不存在'), 400
        old_roles = [r.id for r in user.roles]
        roles = args['role_id']
        to_add_roles = set(roles) - set(old_roles)
        to_delete_roles = set(old_roles) - set(roles)

        for roleid in to_add_roles:
            role_ = Roles.query.get(roleid)
            if not role_:
                return false_return(message=f'{roleid} is not exist'), 400
            if role_ not in user.roles:
                user.roles.append(role_)

        for roleid in to_delete_roles:
            role_ = Roles.query.get(roleid)
            if not role_:
                return false_return(message=f'{roleid} is not exist'), 400
            if role_ in user.roles:
                user.roles.remove(role_)

        return success_return(message='修改角色成功')
