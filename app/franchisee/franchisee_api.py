from flask_restplus import Resource, reqparse, cors
from flask import request
from ..models import Permission, Franchisees, FranchiseeScopes, FranchiseeOperators, FranchiseePurchaseOrders, \
    BusinessUnits
from . import franchisee
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, sort_by_order, code_return, submit_return
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id
from ..decorators import permission_required, allow_cross_domain
from ..swagger import return_dict, head_parser, page_parser
from collections import defaultdict

franchisee_ns = default_api.namespace('franchisee', path='/franchisee', description='加盟商')

return_json = franchisee_ns.model('ReturnRegister', return_dict)

franchisee_page_parser = page_parser.copy()
franchisee_page_parser.add_argument('name', request=False, location="args")
franchisee_page_parser.add_argument('Authorization', required=True, location='headers')

franchisee_scopes_page_parser = page_parser.copy()
franchisee_scopes_page_parser.add_argument('franchisee_id', request=False, location="args")
franchisee_scopes_page_parser.add_argument('Authorization', required=True, location='headers')

create_franchisee_parser = reqparse.RequestParser()
create_franchisee_parser.add_argument('name', required=True, help='加盟商名称（64）')
create_franchisee_parser.add_argument('desc', required=True, type=str, help='加盟商公司描述（200）')
create_franchisee_parser.add_argument('phone1', required=True, type=str, help='电话1')
create_franchisee_parser.add_argument('phone2', required=False, type=str, help='电话2')
create_franchisee_parser.add_argument('address', required=True, type=str, help='地址，手工输入')
create_franchisee_parser.add_argument('scopes', type=list, required=False, help='运营范围', location='json')

create_franchisee_scope = reqparse.RequestParser()
create_franchisee_scope.add_argument('province', required=True)
create_franchisee_scope.add_argument('city', required=True)
create_franchisee_scope.add_argument('district')
create_franchisee_scope.add_argument('street', help='街道')

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
employee_bind_appid.add_argument('phone', required=True, help='用户扫描绑定入口，填写手机号验证')


@franchisee_ns.route('')
class FranchiseesAPI(Resource):
    @franchisee_ns.marshal_with(return_json)
    @franchisee_ns.expect(franchisee_page_parser)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """
        获取所有加盟商清单
        """
        args = franchisee_page_parser.parse_args()
        if 'search' not in args.keys():
            args['search'] = {}
        args['search'] = {"name": args['name']}
        return success_return(get_table_data(Franchisees, args), "请求成功")

    @franchisee_ns.doc(body=create_franchisee_parser)
    @franchisee_ns.marshal_with(return_json)
    @permission_required("app.franchisee.FranchiseeAPI.post")
    def post(self, **kwargs):
        """
        新增加盟商
        :param kwargs:
        :return:
        """
        args = create_franchisee_parser.parse_args()
        if Franchisees.query.filter_by(name=args['name']).first():
            return false_return(message="加盟商重名")

        new_one = new_data_obj("Franchisees",
                               **{"name": args['name'],
                                  "desc": args['desc'],
                                  "phone1": args['phone1'],
                                  "phone2": args['phone2'],
                                  "address": args['address']})

        if not new_one or (new_one and not new_one['status']):
            return false_return(message="create franchisee failed")
        else:
            for sid in args['scopes']:
                scope_obj = db.session.query(FranchiseeScopes).with_for_update().filter(
                    FranchiseeScopes.id.__eq__(sid)).first()
                if not scope_obj:
                    return false_return(message=f"{sid}不存在")

                if not scope_obj.franchisee_id:
                    scope_obj.franchisee_id = new_one['obj'].id
                    submit_result = submit_return("bind successful", "bind fail")
                    if submit_result['code'] == 'success':
                        submit_result['data'] = new_one['obj'].id
                    return submit_result
                else:
                    return false_return(message=f"{sid}'s franchisee id is not null")


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

    @franchisee_ns.doc(body=create_franchisee_parser)
    @franchisee_ns.marshal_with(return_json)
    @permission_required("app.franchisee.FranchiseeScopesAPI.post")
    def post(self, **kwargs):
        """新增加盟商运营范围"""
        args = create_franchisee_parser.parse_args()
        new_scope = new_data_obj("FranchiseeScopes",
                                 **{"province": args['province'],
                                    "city": args['city'],
                                    "district": args['district'],
                                    "street": args['street']})
        if new_scope:
            if new_scope.get('status'):
                if submit_return("", "")['code'] == "success":
                    return success_return(data={"id": new_scope['obj'].id})
                else:
                    return false_return(message="运营范围添加失败"), 400
            else:
                if not new_scope['obj']['franchisee_id']:
                    if submit_return("", "")['code'] == "success":
                        return success_return(data={"id": new_scope['obj'].id}, message="运营范围已存在，未绑定加盟商")
                    else:
                        return false_return(message="运营范围添加失败"), 400
                else:
                    return false_return(message="新增范围失败"), 400
        else:
            return false_return(message="新增范围失败"), 400


@franchisee_ns.route('/scopes/<string:scope_id>/franchisee')
class FranchiseeScopeBindAPI(Resource):
    @franchisee_ns.doc(body=put_scope)
    @franchisee_ns.marshal_with(return_json)
    @permission_required(Permission.ADMINISTRATOR)
    def put(self, **kwargs):
        """
        绑定加盟商和运营范围
        """
        args = put_scope.parse_args()
        scope_obj = db.session.query(FranchiseeScopes).with_for_update().filter(
            FranchiseeScopes.id.__eq__(kwargs.get('scope_id'))).first()
        if not scope_obj:
            return false_return(message=f"{kwargs.get('scope_id')} is not exist")

        if not scope_obj.franchisee_id:
            scope_obj.franchisee_id = args['franchisee_id']
            return submit_return("bind successful", "bind fail")
        else:
            return false_return(message=f"{kwargs['scope_id']}'s franchisee id is not null")

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


@franchisee_ns.route('/qrcode/<string:f_id>')
@franchisee_ns.param('f_id', 'Franchisee ID')
@franchisee_ns.expect(head_parser)
class FranchiseeQrcode(Resource):
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.USER, "app.franchisee.FranchiseeQrcode.post"])
    def post(self, **kwargs):
        """公司运营录入完毕产生的二维码入口，用户扫此入口绑定自己微信成为此加盟商的管理员"""
        pass


@franchisee_ns.route('/<string:f_id>/operator')
@franchisee_ns.param('f_id', 'Franchisee ID')
@franchisee_ns.expect(head_parser)
class FranchiseeOperatorsApi(Resource):
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.BU_OPERATOR, "app.franchisee.FranchiseeOperatorsApi.get"])
    def get(self, **kwargs):
        """获取加盟商运营人员"""
        args = franchisee_operator_page_parser.parse_args()
        args['search']['franchisee_id'] = kwargs['f_id']
        return success_return(data=get_table_data(FranchiseeOperators, args))

    @franchisee_ns.doc(body=new_operator)
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.BU_OPERATOR, "app.business_units.PerBUApi.put"])
    def post(self, **kwargs):
        args = new_operator.parse_args()
        new_employee = new_data_obj("FranchiseeOperators", **{"name": args['name'],
                                                              "age": args['age'],
                                                              "job_desc": args['job_desc'],
                                                              "franchisee_id": kwargs['f_id']})
        if not new_employee or (new_employee and not new_employee['status']):
            return false_return(message=f"create user {args['name']} fail")
        return submit_return("create employee success", "create employee fail")


@franchisee_ns.route('/<string:f_id>/operator/<string:operator_id>/bind')
@franchisee_ns.expect(head_parser)
class FranchiseeOperatorBind(Resource):
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.USER, "app.franchisee.FranchiseeOperatorBind.get"])
    def get(self, **kwargs):
        """作为员工二维码入口，姓名和职位不能修改"""
        return success_return(get_table_data_by_id(FranchiseeOperators,
                                                   kwargs['operator_id'],
                                                   appends=['f_name', 'job_name'],
                                                   removes=['age', 'phone', 'phone_validated']))

    @franchisee_ns.doc(body=employee_bind_appid)
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.USER, "app.franchisee.FranchiseeOperatorBind.put"])
    def put(self, **kwargs):
        """
        绑定员工账号和微信APPID，前端页面先验证手机号，stage传bu_employee
        """
        args = employee_bind_appid.parse_args()
        current_user = kwargs.get('current_user')
        f_operator = FranchiseeOperators.query.filter(FranchiseeOperators.id.__eq__(kwargs['employee_id']),
                                                      FranchiseeOperators.franchisee_id.__eq__(kwargs['f_id'])).first()
        f_operator.customer_id = current_user.id
        f_operator.phone = args['phone']
        f_operator.phone_validated = True
        f_operator.age = args['age']
        return submit_return("绑定成功", "绑定失败")

    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.USER, "app.franchisee.FranchiseeOperatorBind.delete"])
    def delete(self, **kwargs):
        pass


@franchisee_ns.route('/dispatch')
@franchisee_ns.expect(head_parser)
class FranchiseeDispatch(Resource):
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.FRANCHISEE_OPERATOR, "app.franchisee.FranchiseeDispatch.post"])
    def post(self, **kwargs):
        # franchisee 发货给business unit。 根据填写提交人员账号来找对应的franchisee id
        current_user = kwargs.get('current_user')
        pass


@franchisee_ns.route('/business_units')
@franchisee_ns.expect(head_parser)
class FranchiseeBU(Resource):
    @franchisee_ns.marshal_with(return_json)
    @permission_required([Permission.FRANCHISEE_MANAGER, "app.franchisee.FranchiseeBU.get"])
    def post(self, **kwargs):
        """加盟商下店铺列表(查看通过自己注册的店铺的列表)"""
        current_user = kwargs.get('current_user')
        if not current_user.franchisee_operator:
            return false_return(message="当前用户无加盟商角色")
        else:
            args = defaultdict(dict)
            args['search']['franchisee_id'] = current_user.franchisee_operator.franchisee_id
            return success_return(data=get_table_data(BusinessUnits, args))
