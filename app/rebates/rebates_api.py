from flask_restplus import Resource, reqparse
from ..models import ShopOrders, Permission, ItemsOrders, Refund, PersonalRebates, Customers
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id, format_decimal
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
from .calc_rebate import self_rebate, calc
from app.type_validation import checkout_sku_type
from ..wechat.pay import weixin_pay
from sqlalchemy import and_
import datetime
from decimal import Decimal

rebates_ns = default_api.namespace('rebates', path='/rebates', description='返佣API')

return_json = rebates_ns.model('ReturnRegister', return_dict)

rebate_page_parser = page_parser.copy()
rebate_page_parser.add_argument('Authorization', required=True, location='headers')

rebate_statistic = rebate_page_parser.copy()
rebate_statistic.add_argument('agent_id', help='代理商ID， customers.id', location='args')
rebate_statistic.add_argument('agent_nickname', help='代理商微信昵称， customers.username', location='args')
rebate_statistic.add_argument('agent_phone', help='代理商手机号, customers.phone', location='args')
rebate_statistic.add_argument('agent_truename', help='代理商真是姓名, customers.true_name', location='args')
rebate_statistic.add_argument('rebate_start_time', type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d'),
                              help='统计开始时间，此时间为支付成功回调的时间。前端页面可设置默认为当月初, 格式%Y-%m-%d', location='args')
rebate_statistic.add_argument('rebate_end_time', type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d'),
                              help='统计结束时间，此时间为支付成功回调的时间。前端页面可设置默认为当月末, 格式%Y-%m-%d', location='args')

rebate_parser = reqparse.RequestParser()
rebate_parser.add_argument("order_id")


@rebates_ns.route('')
@rebates_ns.expect(head_parser)
class RebateApi(Resource):
    @rebates_ns.marshal_with(return_json)
    @rebates_ns.doc(body=rebate_page_parser)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """获取当前登录用户的返佣"""
        args = rebate_page_parser.parse_args()
        args['search'] = {"delete_at": None}
        if not kwargs.get("current_user"):
            return false_return(f"user does not exist"), 403
        return success_return(self_rebate(kwargs['current_user']))


@rebates_ns.route('/statistic')
@rebates_ns.expect(head_parser)
class RebateStatistic(Resource):
    @rebates_ns.marshal_with(return_json)
    @rebates_ns.doc(body=rebate_statistic)
    @permission_required("app.rebates.rebates_api.statistic.get")
    def get(self, **kwargs):
        """后台账户，获取代理商返佣"""
        keys = ('customer_id', 'agent_nickname', 'agent_phone', 'agent_truename')
        args = rebate_statistic.parse_args()
        args['search'] = dict()
        agent_search = list()
        advance_search = list()
        for key in args.keys():
            if key in keys and args[key]:
                args['search'][key] = args[key]
        args['search']['delete_at'] = None

        if args.get('agent_id'):
            agent_search.append(Customers.id.__eq__(args['agent_id']))
        if args.get('agent_nickname'):
            agent_search.append(Customers.username.contains(args['agent_nickname']))
        if args.get('agent_phone'):
            agent_search.append(Customers.phone.contains(args['agent_phone']))
        if args.get('agent_truename'):
            agent_search.append(Customers.true_name.contains(args['agent_truename']))

        if agent_search:
            advance_search.append({"key": "customer_id",
                                   "operator": "in_",
                                   "value": [c.id for c in Customers.query.filter(and_(*agent_search)).all()]})

        if args.get('rebate_start_time') and args.get('rebate_end_time'):
            advance_search.append({"key": "create_at", "operator": "__ge__", "value": args['rebate_start_time']})
            advance_search.append({"key": "create_at", "operator": "__le__", "value": args['rebate_end_time']})

        elif args.get('rebate_start_time') and not args.get('rebate_end_time'):
            start_at = args.get('rebate_start_time')
            args['rebate_end_time'] = start_at.replace(month=start_at.month + 1, day=1) - datetime.timedelta(days=1)
            advance_search.append({"key": "create_at", "operator": "__ge__", "value": args['rebate_start_time']})
            advance_search.append({"key": "create_at", "operator": "__le__", "value": args['rebate_end_time']})

        elif not args.get('rebate_start_time') and args.get('rebate_end_time'):
            return false_return(message="若选择了结束时间，开始时间必选")

        rebate_detail = get_table_data(PersonalRebates,
                                       args,
                                       appends=['customer_info', 'shop_order_verbose'],
                                       advance_search=advance_search)

        for line in rebate_detail['records']:
            line['rebate_value'] = format_decimal(
                Decimal(line['rebate']) / Decimal("100") * Decimal(line['shop_order_verbose']['real_payed_cash_fee']),
                to_str=True)

        return success_return(rebate_detail)


@rebates_ns.route('/test')
@rebates_ns.expect(head_parser)
class RebateTestApi(Resource):
    @rebates_ns.marshal_with(return_json)
    @rebates_ns.doc(body=rebate_parser)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """获取当前登录用户的返佣"""
        args = rebate_parser.parse_args()
        return success_return(calc(args.get("order_id"), kwargs['current_user'], pay_type="MessageRecharge"))
