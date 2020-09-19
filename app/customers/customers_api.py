from flask import request
from flask_restplus import Resource, reqparse
from ..models import Customers, Permission, ExpressAddress, InvitationCode, MemberCards, ShopOrders
from . import customers
from app.frontstage_auth import auths
from .. import db, default_api, logger
from ..common import success_return, false_return, submit_return
from ..public_method import table_fields, get_table_data, get_table_data_by_id, new_data_obj
import datetime
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
from ..public_user_func import modify_user_profile
import requests
from app.wechat.wx_login import WxLogin
import traceback

customers_ns = default_api.namespace('customers', path='/customers',
                                     description='前端用户接口，包括注册、登陆、登出、获取用户信息、用户与角色操作等')

login_parser = reqparse.RequestParser()
login_parser.add_argument('js_code', required=True, help='前端获取的临时code')
login_parser.add_argument('shared_id', help="分享链接中分享者的customer id")

bind_role_parser = reqparse.RequestParser()
bind_role_parser.add_argument('role_id', required=True, type=int, help='customer_role表中的id')

bind_express_addr_parser = reqparse.RequestParser()
bind_express_addr_parser.add_argument('address1', required=True, help='地图中定位的地址')
bind_express_addr_parser.add_argument('address2', help='门牌号')
bind_express_addr_parser.add_argument('postcode', help='邮编, 可为空')
bind_express_addr_parser.add_argument('recipient', required=True, help='收件人姓名')
bind_express_addr_parser.add_argument('recipient_phone', required=True, help='收件人电话')
bind_express_addr_parser.add_argument('is_default', required=True, type=int, choices=[0, 1], default=0, help='是否为默认地址')
bind_express_addr_parser.add_argument('force_default', required=True, type=int, choices=[0, 1], default=0,
                                      help='是否强制为默认地址')

update_express_addr_parser = bind_express_addr_parser.copy()
update_express_addr_parser.replace_argument('city_id', type=int)
update_express_addr_parser.replace_argument('district', type=int)
update_express_addr_parser.replace_argument('address1')
update_express_addr_parser.replace_argument('recipient', help='收件人')
update_express_addr_parser.replace_argument('recipient_phone', help='收件人电话')
update_express_addr_parser.replace_argument('is_default', type=int, choices=[0, 1], default=0, help='是否为默认地址')
update_express_addr_parser.add_argument('force_default', required=True, type=int, choices=[0, 1], default=0,
                                        help='是否强制为默认地址')

update_customer_parser = reqparse.RequestParser()
update_customer_parser.add_argument('phone', help='用户手机号，如需更改，需要发送验证码认证，调用<string:phone>/verify_code 验证',
                                    location='json')
update_customer_parser.add_argument('username', help='登陆用户名', location='json')
update_customer_parser.add_argument('email', help='email', location='json')
update_customer_parser.add_argument('true_name', help='真实姓名', location='json')
update_customer_parser.add_argument('gender', help='性别 0:unknown 1:male, 2:female', location='json')
update_customer_parser.add_argument('password', help='密码', location='json')
update_customer_parser.add_argument('global_address', location='json', help='用户地址')
update_customer_parser.add_argument('profile_photo', location='json', help='用户头像对应的URL')
update_customer_parser.add_argument('Authorization', required=True, location='headers')
update_customer_parser.add_argument('birthday', type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d'),
                                    help="生日，格式'%Y-%m-%d")

return_json = customers_ns.model('ReturnResult', return_dict)

customer_page_parser = page_parser.copy()
customer_page_parser.add_argument('Authorization', required=True, location='headers')


def if_default(sender, force_default):
    now_default = ExpressAddress.query.filter_by(sender=sender, is_default=1, status=1).first()
    if now_default:
        if not force_default:
            return False
        else:
            now_default.is_default = False
            db.session.add(now_default)
            db.session.flush()

    return True


@customers_ns.route('')
class CustomersAPI(Resource):
    @customers_ns.marshal_with(return_json)
    @permission_required([Permission.USER, "app.customers.customers_api.get"])
    @customers_ns.expect(customer_page_parser)
    def get(self, **kwargs):
        """
        获取前端用户信息
        """
        args = customer_page_parser.parse_args()
        return success_return(
            get_table_data(Customers, args, ['role', 'member_info'], ['role_id']), "请求成功")

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
        try:
            args = login_parser.parse_args()
            user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

            wx_login = WxLogin(args['js_code'])
            response = wx_login.response
            response['shared_id'] = args['shared_id']
            logger.debug(response)
            if 'errcode' in response.keys():
                return false_return(response, "请求失败"), 400
            return auths.authenticate(user_ip, **response)
        except Exception as e:
            return false_return(message=str(e)), 400


@customers_ns.route('/<string:customer_id>/role')
@customers_ns.expect(head_parser)
@customers_ns.param("customer_id", "customer's id")
class CustomerRole(Resource):
    @customers_ns.doc(body=bind_role_parser)
    @customers_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def put(self, **kwargs):
        """
        修改指定ID用户的角色
        """
        args = bind_role_parser.parse_args()
        customer = kwargs.get('current_user')
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


@customers_ns.route('/express_address')
@customers_ns.expect(head_parser)
class CustomerExpressAddress(Resource):
    @customers_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """
        指定ID用户快递地址
        """
        current_user = kwargs['current_user']
        if current_user is None:
            return false_return(message="用户未登陆")
        return success_return(
            get_table_data_by_id(Customers, current_user.id, ["express_addresses"], table_fields(Customers)))

    @customers_ns.doc(body=bind_express_addr_parser)
    @customers_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def post(self, **kwargs):
        """
        指定ID用户新增快递地址
        """
        args = bind_express_addr_parser.parse_args()
        args['sender'] = kwargs['current_user'].id
        if not if_default(kwargs['current_user'].id, args['force_default']):
            return false_return("已存在默认地址")
        new_express_address = ExpressAddress()
        db.session.flush()
        for k, v in args.items():
            if hasattr(new_express_address, k) and v is not None:
                setattr(new_express_address, k, v)
        db.session.add(new_express_address)
        return submit_return("添加地址成功", "添加地址失败")


@customers_ns.route('/<string:express_address_id>')
@customers_ns.expect(head_parser)
@customers_ns.param("express_address_id", "express global_address's id")
class UpdateCustomerExpressAddress(Resource):
    @customers_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """
        指定EXPRESS ADDRESS ID获取用户地址
        """
        if kwargs['express_address_id'] in [addr.id for addr in kwargs['current_user'].express_addresses.all() if
                                            addr.status == 1]:
            return success_return(data=get_table_data_by_id(ExpressAddress, kwargs['express_address_id']))
        else:
            return false_return(message="当前用户没有改地址")

    @customers_ns.doc(body=update_express_addr_parser)
    @customers_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def put(self, **kwargs):
        """
        指定ID用户修改快递地址
        """
        args = update_express_addr_parser.parse_args()
        current_user = kwargs['current_user']
        express_address = ExpressAddress.query.filter_by(id=kwargs['express_address_id'],
                                                         sender=current_user.id, status=1).first()
        if not if_default(current_user.id, args['force_default']):
            return false_return("已存在默认地址")

        for k, v in args.items():
            if hasattr(express_address, k) and v:
                setattr(express_address, k, v)
        db.session.add(express_address)
        return submit_return("修改地址成功", "修改地址失败")

    @customers_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def delete(self, **kwargs):
        """
        删除地址
        """
        addr = ExpressAddress.query.get(kwargs['express_address_id'])
        addr.status = 0
        db.session.add(addr)
        return submit_return("删除地址成功", "删除地址失败")


@customers_ns.route('/interests/verbose')
@customers_ns.expect(head_parser)
class CustomerInterestsVerbose(Resource):
    @customers_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        def statistics_orders(related_object):
            child_sql = related_object.orders.filter(ShopOrders.is_pay.__eq__(1), ShopOrders.status.__eq__(1),
                                                     ShopOrders.delete_at.__eq__(None))

            # 下级订单总数
            payed_count = child_sql.count()
            # 下级订单总金额
            payed_fee = sum([c.cash_fee for c in child_sql.all()])
            # 分析订单中封坛数量、金额；瓶装酒数量、金额； 分装数量、金额
            pass

            # 确认用户角色
            child_member_card = related_object.member_card.filter_by(status=1, member_type=1).first()
            if child_member_card:
                # 如果child是代理，那一定是2级代理，这时候找这个二级下下游，就是直客，将这个代理的利益下级的消费都归属到此代理统计下
                grade = child_member_card.grade
                grand_children_market = related_object.children_market
                for grandchild in grand_children_market:
                    grand_sql = grandchild.orders.filter(ShopOrders.is_pay.__eq__(1),
                                                         ShopOrders.status.__eq__(1),
                                                         ShopOrders.delete_at.__eq__(None))
                    payed_count += grand_sql.count()
                    payed_fee += sum(gc.cash_fee for gc in grand_sql.all())
            else:
                grade = 0
            username = f"{related_object.username}({related_object.phone})" if related_object.phone else f"{related_object.username}"
            return {"id": related_object.id,
                    "username": username,
                    "grade": grade,
                    "create_at": str(related_object.create_at),
                    "payed_count": payed_count,
                    "payed_fee": str(payed_fee)}

        try:
            current_user = kwargs['current_user']
            market = current_user.children_market
            invitees = current_user.be_invited
            invitees_list = list()
            market_list = list()
            for child in market:
                # 当前用户的利益下级的订单
                market_list.append(statistics_orders(child))

            for invitee in invitees:
                # 统计不是自己利益下游的被邀请人的订单数量，这种情况只有用户是二级时才有
                if invitee not in market:
                    invitees_list.append(statistics_orders(invitee))

            market_list.extend(invitees_list)
            market_list.sort(key=lambda x: x["payed_fee"], reverse=True)
            return success_return(market_list)
        except Exception as e:
            traceback.print_exc()
            false_return(message=str(e))
