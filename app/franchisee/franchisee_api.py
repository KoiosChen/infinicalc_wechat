from flask_restplus import Resource, reqparse, cors
from flask import request
from ..models import Permission, Franchisees, FranchiseeScopes, FranchiseeOperators, FranchiseePurchaseOrders, \
    BusinessUnits, FranchiseeInventory, BusinessPurchaseOrders, CustomerRoles
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
create_franchisee_parser.add_argument('bank_name', required=False, help='开户行名称')
create_franchisee_parser.add_argument('bank_account', required=False, help='银行账号')
create_franchisee_parser.add_argument('payee', required=False, help='收款人名称')
create_franchisee_parser.add_argument('tax_account', required=False, help='加盟商税号')
create_franchisee_parser.add_argument('scopes', type=list, required=True,
                                      help='运营范围，[{"province": "上海", "city": "上海", "district": "徐汇区", "transaction_price": "1000000"}]',
                                      location='json')

update_franchisee_parser = create_franchisee_parser.copy()
update_franchisee_parser.replace_argument('name', required=False, help='加盟商名称（64）')
update_franchisee_parser.replace_argument('desc', required=False, help='加盟商公司描述（200）')
update_franchisee_parser.replace_argument('phone1', required=False, help='电话1')
update_franchisee_parser.replace_argument('address', required=False, help='地址，手工输入')
update_franchisee_parser.replace_argument('scopes', type=list, required=False,
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
new_operator.add_argument('job_desc', required=True, help='FRANCHISEE_OPERATOR')

update_operator_parser = reqparse.RequestParser()
update_operator_parser.add_argument('name', required=False, help='员工姓名')
update_operator_parser.add_argument('job_desc', required=False, help='店铺员工，传入FRANCHISEE_OPERATOR, FRANCHISEE_MANAGER')
update_operator_parser.add_argument('age', required=False, help='年龄')
update_operator_parser.add_argument('phone', required=False, help='填写手机号验证')

inventory_search_parser = reqparse.RequestParser()
inventory_search_parser.add_argument('sku_id', required=False, type=str, help='需要搜索的sku id', location='args')

inventory_dispatch_parser = reqparse.RequestParser()
inventory_dispatch_parser.add_argument('sku_id', required=True, type=str, help='发货的sku id')
inventory_dispatch_parser.add_argument('amount', required=True, type=int, help='发货数量，此数值不能大于当前库存量')
inventory_dispatch_parser.add_argument('sell_to', required=True, type=str, help='发货目标店铺ID')

inventory_cancel_parser = reqparse.RequestParser()
inventory_cancel_parser.add_argument('id', required=True, type=str, help='加盟商发货ID，franchisee_inventory_id')

dispatch_confirm_parser = reqparse.RequestParser()
dispatch_confirm_parser.add_argument('status', required=True, type=int, help='0,已发货未确认；1， 已发货已确认；2， 已发货未收到')
dispatch_confirm_parser.add_argument('memo', required=False, type=str, help='未启用，后续考虑用来添加备注')

dispatch_parser = reqparse.RequestParser()
dispatch_parser.add_argument("sku_id", required=True, type=str)
dispatch_parser.add_argument("amount", required=True, type=int)
dispatch_parser.add_argument("bu_id", required=True, type=str, help='发给店铺的id')

purchase_parser = page_parser.copy()
purchase_parser.add_argument("status", required=False, type=int, help='0: 已发货未确认，1：已发货已确认, 2:已发货未收到', location='args')
purchase_parser.add_argument('operator', required=False, help='操作人员的ID', location='args')
purchase_parser.add_argument('operate_at', type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d'),
                             help="操作日期，格式'%Y-%m-%d", location='args')


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
        args['search']['delete_at'] = None
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
                                      "address": args['address'],
                                      "bank_name": args.get('bank_name'),
                                      "bank_account": args.get('bank_account'),
                                      "payee": args.get('payee'),
                                      "tax_account": args.get('tax_account')})

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
                        occupied_scopes.append("区域" + "".join(
                            [scope["province"], scope["city"], scope['district']]) + "已有加盟商运营")
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
                    # scene_invitation = generate_code(12)
                    # redis_db.set(scene_invitation, new_one['obj'].id)
                    # redis_db.expire(scene_invitation, 600)
                    # return success_return(data={'scene': 'new_franchisee', 'scene_invitation': scene_invitation})
                    return success_return(data={'new_franchisee': new_one['obj'].id})
                else:
                    raise Exception('添加加盟商失败')
            else:
                raise Exception(occupied_scopes)
        except Exception as e:
            return false_return(message=str(e)), 400


@franchisee_ns.route('/<string:franchisee_id>')
@franchisee_ns.expect(head_parser)
class PerFranchisee(Resource):
    @franchisee_ns.marshal_with(return_json)
    @permission_required(Permission.ADMINISTRATOR)
    def get(self, **kwargs):
        """获取指定加盟商"""
        return success_return(data=get_table_data_by_id(Franchisees, kwargs['franchisee_id'], appends=['scopes']))

    @franchisee_ns.doc(body=update_franchisee_parser)
    @franchisee_ns.marshal_with(return_json)
    @permission_required(Permission.ADMINISTRATOR)
    def put(self, **kwargs):
        """修改加盟商信息"""
        try:
            args = update_franchisee_parser.parse_args()
            franchisee_obj = Franchisees.query.get(kwargs['franchisee_id'])
            occupied_scope = list()
            present_scopes = franchisee_obj.scopes.all()
            target_scopes = list()
            for key in args.keys():
                if key != 'scopes':
                    if hasattr(franchisee_obj, key):
                        setattr(franchisee_obj, key, args[key])
                    else:
                        raise Exception(f"attribute {key} does not exist")
                elif key == 'scopes' and args.get(key):

                    for scope in args['scopes']:
                        new_scope = new_data_obj("FranchiseeScopes", **{"province": scope["province"],
                                                                        "city": scope['city'],
                                                                        "district": scope['district']})
                        if not new_scope:
                            raise Exception("新增FranchiseeScopes表记录失败")
                        target_scopes.append(new_scope['obj'])
                        if new_scope['status']:
                            new_scope['obj'].franchisee_id = franchisee_obj.id
                        elif not new_scope['status']:
                            if new_scope['obj'].franchisee_id is not None and new_scope[
                                'obj'].franchisee_id != franchisee_obj.id:
                                occupied_scope.append("区域" + "".join(
                                    [scope["province"], scope["city"], scope['district']]) + "已有加盟商运营")
                            else:
                                new_scope['obj'].franchisee_id = franchisee_obj.id
                                new_scope['obj'].delete_at = None
            if not occupied_scope:
                delete_scopes = (set(present_scopes) | set(target_scopes)) - set(target_scopes)
                for ds in delete_scopes:
                    ds.franchisee_id = None
                    ds.delete_at = datetime.datetime.now()
                return submit_return("加盟商修改成功", "加盟商修改失败")
            else:
                return false_return(data=occupied_scope, message="所选运营区域有冲突")
        except Exception as e:
            return false_return(message=str(e))

    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.ADMINISTRATOR, "app.franchisee.FranchiseeOperatorBind.delete"])
    def delete(self, **kwargs):
        """删除加盟商"""
        franchisee_id = kwargs['franchisee_id']
        f_obj = Franchisees.query.get(franchisee_id)
        f_obj.delete_at = datetime.datetime.now()
        return submit_return("删除成功", "删除失败")


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
@franchisee_ns.expect(head_parser)
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


@franchisee_ns.route('/operator')
@franchisee_ns.expect(head_parser)
class FranchiseeOperatorsApi(Resource):
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.FRANCHISEE_MANAGER, "app.franchisee.FranchiseeOperatorsApi.get"])
    def get(self, **kwargs):
        """获取加盟商运营人员"""
        args = franchisee_operator_page_parser.parse_args()
        args['search'] = {'franchisee_id': kwargs['current_user'].franchisee_operator.franchisee_id,
                          'delete_at': None}
        return success_return(data=get_table_data(FranchiseeOperators, args, appends=['increased_bu']))

    @franchisee_ns.doc(body=new_operator)
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.FRANCHISEE_MANAGER, "app.business_units.PerBUApi.put"])
    def post(self, **kwargs):
        args = new_operator.parse_args()
        franchisee_id = kwargs['current_user'].franchisee_operator.franchisee_id
        # job_name = args['job_desc']
        job_name = "FRANCHISEE_OPERATOR"
        fid = CustomerRoles.query.filter_by(name=job_name).first().id
        new_employee = new_data_obj("FranchiseeOperators", **{"name": args['name'],
                                                              "age": args['age'],
                                                              "job_desc": fid,
                                                              "franchisee_id": franchisee_id})
        if not new_employee or (new_employee and not new_employee['status']):
            return false_return(message=f"create user {args['name']} fail")
        else:
            if session_commit().get('code') == 'success':
                return success_return(data={'new_franchisee_employee': new_employee['obj'].id})
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
                                                   appends=['franchisee_name', 'job_name'],
                                                   search={"delete_at": None}))

    @franchisee_ns.doc(body=update_operator_parser)
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.USER, "app.franchisee.FranchiseeOperatorBind.put"])
    def put(self, **kwargs):
        """修改员工账号信息"""
        args = update_operator_parser.parse_args()
        current_user = kwargs.get('current_user')
        bu_id = current_user.business_unit_employee.business_unit_id
        bu_employee = FranchiseeOperator.query.filter(FranchiseeOperator.id.__eq__(kwargs['operator_id']),
                                                      FranchiseeOperator.business_unit_id.__eq__(bu_id)).first()
        for k, v in args.items():
            if k == 'job_desc' and v in ('FRANCHISEE_OPERATOR', 'FRANCHISEE_MANAGER'):
                role_obj = CustomerRoles.query.filter_by(name=v).first()
                if not role_obj:
                    return false_return(message="角色不存在"), 400
                bu_employee.role = role_obj

            elif hasattr(bu_employee, k):
                setattr(bu_employee, k, v)
            else:
                return false_return(message="角色属性不存在"), 400
        return submit_return("修改成功", "修改失败")

    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.FRANCHISEE_MANAGER, "app.franchisee.FranchiseeOperatorBind.delete"])
    def delete(self, **kwargs):
        """删除加盟商员工"""
        franchisee_id = kwargs['franchisee_id']
        f_obj = Franchisees.query.get(franchisee_id)
        f_obj.delete_at = datetime.datetime.now()
        return submit_return("删除成功", "删除失败")


@franchisee_ns.route('/inventory')
@franchisee_ns.expect(head_parser)
class FranchiseeInventoryAPI(Resource):
    @franchisee_ns.doc(body=inventory_search_parser)
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.FRANCHISEE_MANAGER, "app.franchisee.FranchiseeInventoryAPI.get"])
    def get(self, **kwargs):
        """获取该加盟商当前库存"""
        current_user = kwargs.get('current_user')
        franchisee_id = current_user.franchisee_operator.franchisee_id
        args = inventory_search_parser.parse_args()
        if args.get('sku_id'):
            args['search'] = {'sku_id': args.pop('sku_id'), 'franchisee_id': franchisee_id}
        else:
            args['search'] = {'franchisee_id': franchisee_id}
        return success_return(data=get_table_data(FranchiseeInventory, args, appends=['sku']))

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
                                                                                 "amount": -amount,
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

        # 恢复库存, 因为出库单记录的是负值，所以这里用减去
        franchisee_inventory_obj.amount -= franchisee_purchase_order_obj.amount
        return submit_return("出库单取消成功", "出库单取消失败")


@franchisee_ns.route('/business_units')
@franchisee_ns.expect(head_parser)
class FranchiseeBU(Resource):
    @franchisee_ns.marshal_with(return_json)
    @permission_required(Permission.FRANCHISEE_OPERATOR)
    def get(self, **kwargs):
        """加盟商下店铺列表(查看通过自己注册的店铺的列表)"""
        current_user = kwargs.get('current_user')
        manager_role_id = CustomerRoles.query.filter_by(name='FRANCHISEE_MANAGER').first().id
        if not current_user.franchisee_operator:
            return false_return(message="当前用户无加盟商角色")
        else:
            args = defaultdict(dict)
            args['search']['franchisee_id'] = current_user.franchisee_operator.franchisee_id
            if current_user.franchisee_operator.job_desc != manager_role_id:
                args['search']['franchisee_operator_id'] = current_user.franchisee_operator.id
            return success_return(data=get_table_data(BusinessUnits, args, appends=['bu_inventory']))


@franchisee_ns.route('/purchase_orders/<string:franchisee_purchase_order_id>/confirm')
@franchisee_ns.param('franchisee_purchase_order_id', '货单ID')
@franchisee_ns.expect(head_parser)
class FranchiseePurchaseOrdersAPI(Resource):
    @franchisee_ns.doc(body=dispatch_confirm_parser)
    @franchisee_ns.marshal_with(return_json)
    @permission_required(Permission.FRANCHISEE_MANAGER)
    def put(self, **kwargs):
        """修改入库记录状态，如果修改为已收货并确认，则将入库单货物计入库存量中"""
        args = dispatch_confirm_parser.parse_args()
        status = args['status']
        current_user = kwargs.get('current_user')
        if not current_user.franchisee_operator:
            return false_return(message="当前用户无加盟商角色")

        franchisee_id = current_user.franchisee_operator.franchisee_id
        fpo_obj = FranchiseePurchaseOrders.query.get(kwargs['franchisee_purchase_order_id'])
        fi_obj = new_data_obj("FranchiseeInventory",
                              **{"sku_id": fpo_obj.sku_id,
                                 "franchisee_id": franchisee_id})

        if not fi_obj:
            return false_return(message="获取加盟商库存失败")

        if fpo_obj.status in (1, 2) or fpo_obj.delete_at is not None:
            return false_return(message="该货单状态异常不可确认")

        if status == 1:
            fpo_obj.status = status
            fpo_obj.original_order.dispatch_status = status
            fi_obj['obj'].amount += fpo_obj.amount

        return submit_return("确认成功", "确认失败")


@franchisee_ns.route('/purchase_orders')
@franchisee_ns.expect(head_parser)
class GetFranchiseePurchaseOrdersAPI(Resource):
    @franchisee_ns.doc(body=purchase_parser)
    @franchisee_ns.marshal_with(return_json)
    @permission_required(Permission.FRANCHISEE_MANAGER)
    def get(self, **kwargs):
        """获取所有出入库单"""
        args = purchase_parser.parse_args()
        current_user = kwargs.get('current_user')
        if not current_user.franchisee_operator:
            logger.debug("not franchisee")
            return false_return(message="当前用户无加盟商角色")
        franchisee_id = current_user.franchisee_operator.franchisee_id
        args['search'] = dict()
        for k, v in args.items():
            if k in ('status', 'operator', 'operate_at') and v:
                args['search'][k] = v
        args['search']['delete_at'] = None
        args['search']['franchisee_id'] = franchisee_id
        data = get_table_data(FranchiseePurchaseOrders, args, appends=['original_order', 'downstream', 'sku'],
                              removes=['franchisee_id', 'sku_id', 'purchase_from'],
                              advance_search=[
                                  {"key": "FranchiseePurchaseOrders.status", "operator": "__lt__", "value": 3}])
        logger.debug(data)
        return success_return(data=data)


@franchisee_ns.route('/purchase_orders/dispatch')
@franchisee_ns.expect(head_parser)
class FranchiseeDispatch(Resource):
    @franchisee_ns.doc(body=dispatch_parser)
    @franchisee_ns.marshal_with(return_json)
    @permission_required(Permission.FRANCHISEE_MANAGER)
    def post(self, **kwargs):
        """加盟商发货给店铺"""
        args = dispatch_parser.parse_args()
        sku_id = args['sku_id']
        bu_id = args['bu_id']
        amount = args['amount']
        current_user = kwargs['current_user']
        franchisee_id = current_user.franchisee_operator.franchisee_id
        fi_obj = db.session.query(FranchiseeInventory).with_for_update().filter(
            FranchiseeInventory.sku_id.__eq__(sku_id), FranchiseeInventory.franchisee_id.__eq__(franchisee_id),
            FranchiseeInventory.amount.__ge__(amount)).first()
        if not fi_obj:
            return false_return(message="加盟商库存不足")

        new_franchisee_dispatch = new_data_obj("FranchiseePurchaseOrders",
                                               **{"franchisee_id": franchisee_id,
                                                  "sku_id": sku_id,
                                                  "amount": -amount,
                                                  "sell_to": bu_id,
                                                  "operator": current_user.id,
                                                  "operate_at": datetime.datetime.now()})
        if not new_franchisee_dispatch:
            return false_return(message="创建发货单失败")

        new_bu_purchase_order = new_data_obj("BusinessPurchaseOrders",
                                             **{"bu_id": bu_id, "amount": amount,
                                                "original_order_id": new_franchisee_dispatch['obj'].id,
                                                "operate_at": datetime.datetime.now(),
                                                "operator": current_user.id})

        if not new_bu_purchase_order:
            return false_return(message="创建入库单失败")

        fi_obj.amount -= amount
        return submit_return("加盟商出库到店铺成功", "出库失败")


@franchisee_ns.route('/statistics/<string:scene>')
@franchisee_ns.param('scene', "pickup或者sold。Pickup指取酒的统计。sold指卖掉的酒且是消费者首单的酒")
@franchisee_ns.expect(head_parser)
class FranchiseeStatistics(Resource):
    @franchisee_ns.marshal_with(return_json)
    # @franchisee_ns.doc(body=sold_parser)
    @permission_required(Permission.BU_WAITER)
    def get(self, **kwargs):
        """店铺卖掉的酒"""
        pass
