from flask import request
from flask_restplus import Resource, reqparse
from ..models import Customers, Permission, ExpressAddress
from . import customers
from app.frontstage_auth import auths
from .. import db, default_api, logger
from ..common import success_return, false_return, submit_return
from ..public_method import table_fields, get_table_data, get_table_data_by_id
import datetime
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
from ..public_user_func import modify_user_profile
import requests
from app.wechat.wx_login import WxLogin

customers_ns = default_api.namespace('customers', path='/customers',
                                     description='前端用户接口，包括注册、登陆、登出、获取用户信息、用户与角色操作等')

login_parser = reqparse.RequestParser()
login_parser.add_argument('js_code', required=True, help='前端获取的临时code')

bind_role_parser = reqparse.RequestParser()
bind_role_parser.add_argument('role_id', required=True, type=int, help='customer_role表中的id')

bind_express_addr_parser = reqparse.RequestParser()
bind_express_addr_parser.add_argument('city_id', type=int, required=True)
bind_express_addr_parser.add_argument('district', type=int, required=True)
bind_express_addr_parser.add_argument('address1', required=True)
bind_express_addr_parser.add_argument('address2')
bind_express_addr_parser.add_argument('postcode', help='邮编')
bind_express_addr_parser.add_argument('recipients', required=True, help='收件人姓名')
bind_express_addr_parser.add_argument('recipients_phone', required=True, help='收件人电话')
bind_express_addr_parser.add_argument('is_default', required=True, type=int, choices=[0, 1], default=0, help='是否为默认地址')

update_express_addr_parser = bind_express_addr_parser.copy()
update_express_addr_parser.replace_argument('city_id', type=int)
update_express_addr_parser.replace_argument('district', type=int)
update_express_addr_parser.replace_argument('address1')
update_express_addr_parser.replace_argument('recipients', help='收件人')
update_express_addr_parser.replace_argument('recipients_phone', help='收件人电话')
update_express_addr_parser.replace_argument('is_default', type=int, choices=[0, 1], default=0, help='是否为默认地址')

update_customer_parser = reqparse.RequestParser()
update_customer_parser.add_argument('phone', help='用户手机号，如需更改，需要发送验证码认证，调用<string:phone>/verify_code 验证',
                                    location='json')
update_customer_parser.add_argument('username', help='登陆用户名', location='json')
update_customer_parser.add_argument('email', help='email', location='json')
update_customer_parser.add_argument('true_name', help='真实姓名', location='json')
update_customer_parser.add_argument('gender', help='性别 0:unknown 1:male, 2:female', location='json')
update_customer_parser.add_argument('password', help='密码', location='json')
update_customer_parser.add_argument('global_address', location='json', help='用户地址')
update_customer_parser.add_argument('profile_photo', location='json', help='用户头像对应的obj_storage中的ID')
update_customer_parser.add_argument('Authorization', required=True, location='headers')
update_customer_parser.add_argument('birthday', type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d'),
                                    help="生日，格式'%Y-%m-%d")

return_json = customers_ns.model('ReturnResult', return_dict)

customer_page_parser = page_parser.copy()
customer_page_parser.add_argument('Authorization', required=True, location='headers')


@customers_ns.route('')
class CustomersAPI(Resource):
    @customers_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    @customers_ns.expect(customer_page_parser)
    def get(self, **kwargs):
        """
        获取前端用户信息
        """
        args = customer_page_parser.parse_args()
        return success_return(
            get_table_data(Customers, args, ['role'], ['role_id']), "请求成功")

    @customers_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    @customers_ns.doc(body=update_customer_parser)
    def put(self, **kwargs):
        """
        修改前端用户属性
        """
        args = update_customer_parser.parse_args()
        user = kwargs['current_user']
        fields_ = table_fields(Customers, appends=[], removes=['role_id'])
        return modify_user_profile(args, user, fields_)


@customers_ns.route('/login')
class Login(Resource):
    @customers_ns.doc(body=login_parser)
    @customers_ns.marshal_with(return_json)
    def post(self):
        """
        用户登陆，获取OPEN_ID
        """
        args = login_parser.parse_args()
        user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

        wx_login = WxLogin(args['js_code'])
        response = wx_login.response
        logger.debug(response)
        if 'errcode' in response.keys():
            return false_return(response, "请求失败"), 400
        return auths.authenticate(user_ip, **response)


@customers_ns.route('/<string:customer_id>/role')
@customers_ns.expect(head_parser)
@customers_ns.param("customer_id", "customer's id")
class CustomerRole(Resource):
    @customers_ns.doc(body=bind_role_parser)
    @customers_ns.marshal_with(return_json)
    @permission_required(Permission.OPERATOR)
    def put(self, **kwargs):
        """
        修改指定ID用户的角色
        """
        args = bind_role_parser.parse_args()
        customer = Customers.query.get(kwargs.get('customer_id'))
        if not customer:
            return false_return(message='用户不存在'), 400
        old_role = customer.role
        new_role = Customers.query.get(args['role_id'])
        if new_role:
            customer.role = new_role
            db.session.add(customer)
            logger.info(f">>> Alert old role {old_role.id}: {old_role.name} to new role id {new_role}")
            return submit_return('修改角色成功', "修改角色失败")
        else:
            return false_return(f'变更目标角色ID: {args["role_id"]}不存在'), 400


@customers_ns.route('/<string:customer_id>/express_address')
@customers_ns.expect(head_parser)
@customers_ns.param("customer_id", "customer's id")
class CustomerExpressAddress(Resource):
    @customers_ns.marshal_with(return_json)
    @permission_required(Permission.OPERATOR)
    def get(self, **kwargs):
        """
        指定ID用户快递地址
        """
        return success_return(
            get_table_data_by_id(Customers, kwargs['customer_id'], ["express_addresses"], table_fields(Customers)))

    @customers_ns.doc(body=bind_express_addr_parser)
    @customers_ns.marshal_with(return_json)
    @permission_required(Permission.OPERATOR)
    def post(self, **kwargs):
        """
        指定ID用户新增快递地址
        """
        args = bind_express_addr_parser.parse_args()
        args['sender'] = kwargs['customer_id']
        new_express_address = ExpressAddress()
        db.session.flush()
        for k, v in args.items():
            if hasattr(new_express_address, k) and v:
                setattr(new_express_address, k, v)
        db.session.add(new_express_address)
        return submit_return("添加地址成功", "添加地址失败")


@customers_ns.route('/<string:customer_id>/<string:express_address_id>')
@customers_ns.expect(head_parser)
@customers_ns.param("customer_id", "customer's id")
@customers_ns.param("express_address_id", "express global_address's id")
class UpdateCustomerExpressAddress(Resource):
    @customers_ns.doc(body=update_express_addr_parser)
    @customers_ns.marshal_with(return_json)
    @permission_required(Permission.OPERATOR)
    def put(self, **kwargs):
        """
        指定ID用户修改快递地址
        """
        args = update_express_addr_parser.parse_args()
        express_address = ExpressAddress.query.filter_by(id=kwargs['express_address_id'],
                                                         sender=kwargs['customer_id']).first()

        for k, v in args.items():
            if hasattr(express_address, k) and v:
                setattr(express_address, k, v)
        db.session.add(express_address)
        return submit_return("修改地址成功", "修改地址失败")
