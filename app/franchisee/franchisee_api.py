from flask_restplus import Resource, reqparse, cors
from flask import request
from ..models import Permission, Franchisees, FranchiseeScopes, FranchiseeOperators, FranchiseePurchaseOrders, \
    BusinessUnits, FranchiseeInventory, BusinessPurchaseOrders
from . import franchisee
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, sort_by_order, code_return, submit_return
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id
from ..decorators import permission_required, allow_cross_domain
from ..swagger import return_dict, head_parser, page_parser
from collections import defaultdict
from app.scene_invitation.scene_invitation_api import generate_code
import datetime

franchisee_ns = default_api.namespace('franchisee', path='/franchisee', description='加盟商')

return_json = franchisee_ns.model('ReturnRegister', return_dict)

franchisee_page_parser = page_parser.copy()
franchisee_page_parser.add_argument('name', required=False, location="args")
franchisee_page_parser.add_argument('Authorization', required=True, location='headers')

franchisee_scopes_page_parser = page_parser.copy()
franchisee_scopes_page_parser.add_argument('franchisee_id', required=False, location="args")
franchisee_scopes_page_parser.add_argument('Authorization', required=True, location='headers')

create_franchisee_parser = reqparse.RequestParser()
create_franchisee_parser.add_argument('name', required=True, help='加盟商名称（64）')
create_franchisee_parser.add_argument('desc', required=True, type=str, help='加盟商公司描述（200）')
create_franchisee_parser.add_argument('phone1', required=True, type=str, help='电话1')
create_franchisee_parser.add_argument('phone2', required=False, type=str, help='电话2')
create_franchisee_parser.add_argument('address', required=True, type=str, help='地址，手工输入')
create_franchisee_parser.add_argument('scopes', type=list, required=True,
                                      help='运营范围，[{"province": "上海", "city": "上海", "district": "徐汇区"}]',
                                      location='json')

create_franchisee_scope = reqparse.RequestParser()
create_franchisee_scope.add_argument('province', required=True)
create_franchisee_scope.add_argument('city', required=True)
create_franchisee_scope.add_argument('district', required=True)

put_scope = reqparse.RequestParser()
put_scope.add_argument('franchisee_id', required=True)

franchisee_operator_page_parser = page_parser.copy()

new_operator = reqparse.RequestParser()
new_operator.add_argument('name', required=True, type=str, help='运营人员姓名')
new_operator.add_argument('age', required=False, type=int, help='年龄')
new_operator.add_argument('job_desc', required=True, type=int, default=1, choices=[1, 2, 3],
                          help='1: boss, 2: leader, 3: waiter')

employee_bind_appid = reqparse.RequestParser()
employee_bind_appid.add_argument('age', required=False, help='年龄')
employee_bind_appid.add_argument('phone', required=False, help='填写手机号验证')

inventory_search_parser = reqparse.RequestParser()
inventory_search_parser.add_argument('sku_id', required=False, type=str, help='需要搜索的sku id')

inventory_dispatch_parser = reqparse.RequestParser()
inventory_dispatch_parser.add_argument('sku_id', required=True, type=str, help='发货的sku id')
inventory_dispatch_parser.add_argument('amount', required=True, type=int, help='发货数量，此数值不能大于当前库存量')
inventory_dispatch_parser.add_argument('sell_to', required=True, type=str, help='发货目标店铺ID')

inventory_cancel_parser = reqparse.RequestParser()
inventory_cancel_parser.add_argument('id', required=True, type=str, help='加盟商发货ID，franchisee_inventory_id')


@franchisee_ns.route('')
@franchisee_ns.expect(head_parser)
class FranchiseesAPI(Resource):
    @franchisee_ns.marshal_with(return_json)
    @franchisee_ns.expect(franchisee_page_parser)
    @permission_required(Permission.ADMINISTRATOR)
    def get(self, **kwargs):
        """
        获取所有加盟商清单
        """
        args = franchisee_page_parser.parse_args()
        if 'search' not in args.keys():
            args['search'] = {}
        if args.get('name'):
            args['search'] = {"name": args['name']}
        return success_return(get_table_data(Franchisees, args), "请求成功")

    @franchisee_ns.doc(body=create_franchisee_parser)
    @franchisee_ns.marshal_with(return_json)
    @permission_required(Permission.ADMINISTRATOR)
    def post(self, **kwargs):
        """新增加盟商"""
        try:
            args = create_franchisee_parser.parse_args()
            if Franchisees.query.filter_by(name=args['name']).first():
                raise Exception("加盟商重名")

            new_one = new_data_obj("Franchisees",
                                   **{"name": args['name'],
                                      "desc": args['desc'],
                                      "phone1": args['phone1'],
                                      "phone2": args['phone2'],
                                      "address": args['address']})

            occupied_scopes = list()

            db.session.flush()

            if not new_one or (new_one and not new_one['status']):
                raise Exception("新增加盟商失败")
            else:
                for scope in args['scopes']:
                    scope_obj = db.session.query(FranchiseeScopes).with_for_update().filter(
                        FranchiseeScopes.province.__eq__(scope['province']),
                        FranchiseeScopes.city.__eq__(scope.get('city')),
                        FranchiseeScopes.district.__eq__(scope.get('district'))
                    ).first()

                    if scope_obj and scope_obj.franchisee_id is not None:
                        occupied_scopes.append = "区域" + "".join(
                            [scope["province"], scope["city"], scope['district']]) + "已有加盟商运营"
                    else:
                        new_scope = new_data_obj('FranchiseeScopes',
                                                 **{"province": scope["province"],
                                                    "city": scope['city'],
                                                    "district": scope['district'],
                                                    "franchisee_id": new_one['obj'].id})
                        if not new_scope or not new_scope['status']:
                            raise Exception('创建运营范围失败')
            if not occupied_scopes:
                if session_commit().get('code') == 'success':
                    scene_invitation = generate_code(12)
                    redis_db.set(scene_invitation, new_one['obj'].id)
                    redis_db.expire(scene_invitation, 600)
                    return success_return(data={'scene': 'new_franchisee', 'scene_invitation': scene_invitation})
                else:
                    raise Exception('添加加盟商失败')
            else:
                return false_return(data=occupied_scopes, message='部分运营范围不可用'), 400
        except Exception as e:
            return false_return(message=str(e)), 400


@franchisee_ns.route('/scopes')
class FranchiseeScopesAPI(Resource):
    @franchisee_ns.marshal_with(return_json)
    @franchisee_ns.expect(franchisee_scopes_page_parser)
    @permission_required(Permission.ADMINISTRATOR)
    def get(self, **kwargs):
        """
        获取加盟商运营范围
        """
        args = franchisee_scopes_page_parser.parse_args()
        if 'franchisee_id' in args.keys():
            args["search"]["franchisee_id"] = args['franchisee_id']
        return success_return(get_table_data(FranchiseeScopes, args, removes=['franchisee_id']))


@franchisee_ns.route('/scopes/<string:scope_id>/franchisee')
class FranchiseeScopeBindAPI(Resource):
    @franchisee_ns.doc(body=put_scope)
    @franchisee_ns.marshal_with(return_json)
    @permission_required(Permission.ADMINISTRATOR)
    def delete(self, **kwargs):
        """
        拆开加盟商和运营范围绑定关系，将运营范围的franchisee_id置为null
        """
        args = put_scope.parse_args()
        scope_obj = db.session.query(FranchiseeScopes).with_for_update().filter(
            FranchiseeScopes.id.__eq__(kwargs.get('scope_id'))).first()
        if scope_obj.franchisee_id == args['franchisee_id']:
            scope_obj.franchisee_id = ""
            return submit_return("unbind successful", "unbind fail")
        else:
            return false_return(message=f"{kwargs['scope_id']}'s franchisee id is not null")


@franchisee_ns.route('/<string:f_id>/operator')
@franchisee_ns.param('f_id', 'Franchisee ID')
@franchisee_ns.expect(head_parser)
class FranchiseeOperatorsApi(Resource):
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.FRANCHISEE_MANAGER, "app.franchisee.FranchiseeOperatorsApi.get"])
    def get(self, **kwargs):
        """获取加盟商运营人员"""
        args = franchisee_operator_page_parser.parse_args()
        args['search']['franchisee_id'] = kwargs['f_id']
        return success_return(data=get_table_data(FranchiseeOperators, args))

    @franchisee_ns.doc(body=new_operator)
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.FRANCHISEE_MANAGER, "app.business_units.PerBUApi.put"])
    def post(self, **kwargs):
        args = new_operator.parse_args()
        new_employee = new_data_obj("FranchiseeOperators", **{"name": args['name'],
                                                              "age": args['age'],
                                                              "job_desc": args['job_desc'],
                                                              "franchisee_id": kwargs['f_id']})
        if not new_employee or (new_employee and not new_employee['status']):
            return false_return(message=f"create user {args['name']} fail")
        else:
            if session_commit().get('code') == 'success':
                scene_invitation = generate_code(12)
                redis_db.set(scene_invitation, new_employee['obj'].id)
                redis_db.expire(scene_invitation, 600)
                return success_return(data={'scene': 'new_franchisee_employee',
                                            'scene_invitation': scene_invitation})
            else:
                return false_return("create employee fail")


@franchisee_ns.route('/operator/<string:operator_id>')
@franchisee_ns.expect(head_parser)
class FranchiseeOperator(Resource):
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.FRANCHISEE_MANAGER, "app.franchisee.FranchiseeOperatorBind.get"])
    def get(self, **kwargs):
        """查询店铺下指定员工的详情"""
        return success_return(get_table_data_by_id(FranchiseeOperators,
                                                   kwargs['operator_id'],
                                                   appends=['f_name', 'job_name']))

    @franchisee_ns.doc(body=employee_bind_appid)
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.USER, "app.franchisee.FranchiseeOperatorBind.put"])
    def put(self, **kwargs):
        """
        修改店铺员工信息
        """
        args = employee_bind_appid.parse_args()
        current_user = kwargs.get('current_user')
        f_operator = FranchiseeOperators.query.filter(FranchiseeOperators.id.__eq__(kwargs['employee_id']),
                                                      FranchiseeOperators.franchisee_id.__eq__(kwargs['f_id'])).first()
        f_operator.customer_id = current_user.id
        if args.get('phone'):
            f_operator.phone = args['phone']
            f_operator.phone_validated = True
        f_operator.age = args.get('age')
        return submit_return("修改成功", "修改失败")

    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.FRANCHISEE_MANAGER, "app.franchisee.FranchiseeOperatorBind.delete"])
    def delete(self, **kwargs):
        pass


@franchisee_ns.route('/inventory')
@franchisee_ns.expect(head_parser)
class FranchiseeInventoryAPI(Resource):
    @franchisee_ns.doc(body=inventory_search_parser)
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.FRANCHISEE_MANAGER, "app.franchisee.FranchiseeInventoryAPI.get"])
    def get(self, **kwargs):
        """获取该加盟商当前库存"""
        args = inventory_search_parser.parse_args()
        if args.get('sku_id'):
            search = {"sku_id": args['sku_id']}
        else:
            search = None
        current_user = kwargs.get('current_user')
        franchisee_id = current_user.franchisee_operator.franchisee_id
        return success_return(data=get_table_data_by_id(FranchiseeInventory, franchisee_id, search=search))

    @franchisee_ns.doc(body=inventory_dispatch_parser)
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.FRANCHISEE_MANAGER, "app.franchisee.FranchiseeInventoryAPI.post"])
    def post(self, **kwargs):
        # franchisee 发货给business unit。 根据填写提交人员账号来找对应的franchisee id
        try:
            args = inventory_dispatch_parser.parse_args()
            amount = args.get('amount')
            sku_id = args.get('sku_id')
            sell_to = args.get('sell_to')
            current_user = kwargs.get('current_user')
            franchisee_id = current_user.franchisee_operator.franchisee_id

            inventory_obj = db.session.query(FranchiseeInventory).with_for_update().filter(
                FranchiseeInventory.franchisee_id.__eq__(franchisee_id),
                FranchiseeInventory.sku_id.__eq__(sku_id),
                FranchiseeInventory.amount.__ge__(amount)
            ).first()

            if not inventory_obj:
                raise Exception("无库存")
            else:
                inventory_obj.amount -= amount
                new_purchase_order = new_data_obj("FranchiseePurchaseOrders", **{"franchisee_id": franchisee_id,
                                                                                 "sku_id": sku_id,
                                                                                 "amount": amount,
                                                                                 "purchase_from": None,
                                                                                 "sell_to": sell_to,
                                                                                 "operate_at": datetime.datetime.now(),
                                                                                 "operator": current_user.id})
                if not new_purchase_order:
                    raise Exception("创建加盟商出库单失败")

                new_bu_purchase_order = new_data_obj("BusinessPurchaseOrders",
                                                     **{"bu_id": sell_to,
                                                        "amount": amount,
                                                        "purchase_from": franchisee_id,
                                                        "original_order_id": new_purchase_order['obj'].id})

                if not new_bu_purchase_order:
                    raise Exception("创建店铺入库单失败")

                return submit_return(f"加盟商{current_user.franchisee_operator.franchisee.name}出库{sku_id} {amount}瓶成功",
                                     f"加盟商{current_user.franchisee_operator.franchisee.name}出库{sku_id} {amount}瓶失败，数据库提交错误")

        except Exception as e:
            return false_return(message=str(e)), 400

    @franchisee_ns.doc(body=inventory_cancel_parser)
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.FRANCHISEE_MANAGER, "app.franchisee.FranchiseeInventoryAPI.delete"])
    def delete(self, **kwargs):
        """如果status是0，则可以取消该发货订单"""
        args = inventory_cancel_parser.parse_args()
        current_user = kwargs.get('current_user')
        franchisee_id = current_user.franchisee_operator.franchisee_id
        fpo_id = args.get('id')
        # 获取加盟商进货单数据
        franchisee_purchase_order_obj = FranchiseePurchaseOrders.query.filter_by(id=fpo_id, status=0).first()

        # 获取对应店铺入库单，切状态是0，并且锁定此行
        bu_purchase_order_obj = db.session.query(BusinessPurchaseOrders).with_for_update().filter(
            BusinessPurchaseOrders.original_order_id.__eq__(fpo_id),
            BusinessPurchaseOrders.status.__eq__(0)
        ).first()

        # 获取加盟商库存量，并且锁定此行
        franchisee_inventory_obj = db.session.query(FranchiseeInventory).filter(
            FranchiseeInventory.sku_id == franchisee_purchase_order_obj.sku_id,
            FranchiseeInventory.franchisee_id == franchisee_purchase_order_obj.franchisee_id).first()

        if not franchisee_purchase_order_obj:
            return false_return(message="当前订单不可取消，请联系公司客户"), 400

        # 删除出库单
        franchisee_purchase_order_obj.delete_at = datetime.datetime.now()

        # 删除入库单
        bu_purchase_order_obj.delete_at = datetime.datetime.now()

        # 恢复库存
        franchisee_inventory_obj.amount += franchisee_purchase_order_obj.amount
        return submit_return("出库单取消成功", "出库单取消失败")


@franchisee_ns.route('/business_units')
@franchisee_ns.expect(head_parser)
class FranchiseeBU(Resource):
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.FRANCHISEE_MANAGER, "app.franchisee.FranchiseeBU.get"])
    def get(self, **kwargs):
        """加盟商下店铺列表(查看通过自己注册的店铺的列表)"""
        current_user = kwargs.get('current_user')
        if not current_user.franchisee_operator:
            return false_return(message="当前用户无加盟商角色")
        else:
            args = defaultdict(dict)
            args['search']['franchisee_id'] = current_user.franchisee_operator.franchisee_id
            return success_return(data=get_table_data(BusinessUnits, args))
