from flask import jsonify, request
from flask_restplus import Resource, fields, reqparse
from ..models import Users, Roles, Customers
from . import customers
from app.frontstage_auth import auths
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
from ..public_method import table_fields, new_data_obj
import datetime
from ..decorators import permission_required
from ..swagger import return_dict, head_parser

customers_ns = default_api.namespace('customers', path='/customers',
                                     description='前端用户接口，包括注册、登陆、登出、获取用户信息、用户与角色操作等')

register_parser = reqparse.RequestParser()
register_parser.add_argument('phone', required=True, help='用户注册用的手机', location='json')
register_parser.add_argument('verify_code', required=True, help='验证码', location='json')
register_parser.add_argument('role_id', help='用户角色, 可多个，用list来传递。如果不传递，则为默认普通用户权限', location='json', type=list)

login_parser = reqparse.RequestParser()
login_parser.add_argument('username', required=True, help='微信unionid | 手机号 | 用户名')
login_parser.add_argument('password', required=True, help='当为unionid时，不需要密码；当为手机号时，需要传递短信验证码；当为用户名时，为用户密码')
login_parser.add_argument('method', required=True, help='可以是password 或 code 或 unionid。 当username传递手机号时为code')
login_parser.add_argument('platform', required=True, help='平台字段， pc | mobile')

bind_role_parser = reqparse.RequestParser()
bind_role_parser.add_argument('role_id', required=True, type=list, location='json', help='选择的结果，role可多选，例如[1,2]')

update_customer_parser = reqparse.RequestParser()
update_customer_parser.add_argument('phone', help='用户手机号，如需更改，需要发送验证码认证，调用<string:phone>/verify_code 验证',
                                    location='json')
update_customer_parser.add_argument('username', help='登陆用户名', location='json')
update_customer_parser.add_argument('email', help='email', location='json')
update_customer_parser.add_argument('true_name', help='真实姓名', location='json')
update_customer_parser.add_argument('gender', help='性别 0:unknown 1:male, 2:female', location='json')
update_customer_parser.add_argument('password', help='密码', location='json')
update_customer_parser.add_argument('role_id', type=list, location='json', help='选择的结果，role可多选，例如[1,2]')
update_customer_parser.add_argument('address', location='json', help='用户地址')
update_customer_parser.add_argument('profile_photo', location='json', help='用户头像对应的img_url中的ID')
update_customer_parser.add_argument('Authorization', required=True, location='headers')
update_customer_parser.add_argument('birthday', type=lambda x: datetime.datetime.strftime(x, '%Y-%m-%d'),
                                    help="生日，格式'%Y-%m-%d")

return_json = customers_ns.model('ReturnRegister', return_dict)


@customers_ns.route('')
class CustomersAPI(Resource):
    @customers_ns.marshal_with(return_json)
    @permission_required("frontstage.app.customers.customers_api.users_info")
    @customers_ns.expect(head_parser)
    def get(self, info):
        """
        获取前端用户信息
        """
        fields_ = table_fields(Customers, ["roles"], ["password_hash"])
        ru = list()
        for customer in Customers.query.all():
            tmp = {}
            for f in fields_:
                if f == 'roles':
                    tmp[f] = {r.id: r.name for r in customer.roles}
                else:
                    tmp[f] = getattr(customer, f)
            ru.append(tmp)
        return success_return(ru, "请求成功")

    @customers_ns.doc(body=register_parser)
    @customers_ns.marshal_with(return_json)
    def post(self):
        """
        前端用户注册
        """
        args = register_parser.parse_args()
        phone = args['phone']
        verify_code = args['verify_code']
        role_ids = args.get('role_id')
        key = f'front::verification_code::{phone}'
        try:
            if redis_db.exists(key) and redis_db.get(key) == verify_code:
                new_customer = new_data_obj('Customers', **{"phone": phone, "status": 1})
                if new_customer and new_customer.get('status'):
                    user = new_customer['obj']
                else:
                    return false_return(message=f"<{phone}>已经存在"), 400

                if not role_ids:
                    role_ids = list()
                    role_ids.append(new_data_obj("Roles", **{"name": "normal_customer"})['obj'].id)

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

    @customers_ns.marshal_with(return_json)
    @permission_required("frontstage.app.customers.customers_api.update_customer_attributes")
    @customers_ns.doc(body=update_customer_parser)
    def put(self, **kwargs):
        """
        修改前端用户属性
        """
        args = update_customer_parser.parse_args()
        user = kwargs['info']['user']
        fields_ = table_fields(Customers, appends=['role_id', 'password'], removes=['password_hash'])
        for f in fields_:
            if f == 'role_id' and args.get(f):
                user.roles = []
                for r in args.get(f):
                    role = Roles.query.get(r)
                    user.roles.append(role)
            elif args.get(f):
                setattr(user, f, args.get(f))
        return success_return(message="更新成功")


@customers_ns.route('/login')
class Login(Resource):
    @customers_ns.doc(body=login_parser)
    @customers_ns.marshal_with(return_json)
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


@customers_ns.route('/logout')
class Logout(Resource):
    @customers_ns.marshal_with(return_json)
    @permission_required("frontstage.app.customers.customers_api.logout")
    @customers_ns.expect(head_parser)
    def post(self, info):
        """
        用户登出
        """
        login_info = info.get('login_info')
        db.session.delete(login_info)
        result = success_return(message="登出成功") if session_commit().get("code") == 'success' else false_return(
            message='登出失败'), 400
        return result


@customers_ns.route('/<string:customer_id>/roles')
@customers_ns.expect(head_parser)
@customers_ns.param("customer_id", "customer's id")
class CustomerRole(Resource):
    @permission_required("frontstage.app.customers.customers_api.bind_role")
    @customers_ns.doc(body=bind_role_parser)
    @customers_ns.marshal_with(return_json)
    def post(self, **kwargs):
        """
        给用户添加角色
        """
        args = bind_role_parser.parse_args()
        user = Customers.query.get(kwargs.get('customer_id'))
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

        db.session.add(user)
        return success_return(message='修改角色成功') if session_commit() else false_return(message="修改角色失败"), 400
