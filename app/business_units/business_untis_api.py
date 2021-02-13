from flask_restplus import Resource, reqparse, cors
from flask import request
from ..models import Permission, BusinessUnits, BusinessPurchaseOrders, BusinessUnitEmployees, BusinessUnitProducts
from . import business_units
from .. import db, redis_db, default_api, logger, image_operate
from ..common import success_return, false_return, session_commit, sort_by_order, code_return, submit_return
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id, geo_distance
from ..decorators import permission_required, allow_cross_domain
from ..swagger import return_dict, head_parser, page_parser
import datetime

bu_ns = default_api.namespace('Business Units', path='/business_units', description='店铺接口')

return_json = bu_ns.model('ReturnRegister', return_dict)

bu_page_parser = page_parser.copy()
bu_page_parser.add_argument('name', required=False, location="args")
bu_page_parser.add_argument('Authorization', required=True, location='headers')

create_bu_parser = reqparse.RequestParser()
create_bu_parser.add_argument('name', required=True, help='店铺名称（64）')
create_bu_parser.add_argument('desc', required=True, type=str, help='店铺描述（200）')
create_bu_parser.add_argument('chain_store_code', required=False, type=str, help='若未连锁店，则填写预定义的code，例如 xyz123')
create_bu_parser.add_argument('phone1', required=True, type=str, help='电话1')
create_bu_parser.add_argument('phone2', required=False, type=str, help='电话2')
create_bu_parser.add_argument('address', required=True, type=str, help='地址，手工输入')
create_bu_parser.add_argument('unit_type', required=True, type=int, choices=[1], default=1, help='1: 餐饮')
create_bu_parser.add_argument('longitude', required=True, type=str, help='经度')
create_bu_parser.add_argument('latitude', required=True, type=str, help='纬度')
create_bu_parser.add_argument('franchisee_id', required=True, type=str, help='加盟商ID， 由注册页面参数带入，餐饮店注册提交时一并提交')
create_bu_parser.add_argument('status', required=True, type=int, default=0, choices=[0, 1],
                              help='默认0，下架（页面不可见）；1，直接上架（页面需要提示用户，“请确认已上传店铺装修图片及产品信息”）')
create_bu_parser.add_argument('decorate_images', type=list, required=False, help='店铺装修图片', location='json')

update_bu_parser = create_bu_parser.copy()
update_bu_parser.replace_argument('name', required=False, help='店铺名称（64）')
update_bu_parser.replace_argument('desc', required=False, type=str, help='店铺描述（200）')
update_bu_parser.add_argument('phone1', required=False, type=str, help='电话1')
update_bu_parser.add_argument('address', required=False, type=str, help='地址，手工输入')
update_bu_parser.add_argument('unit_type', required=False, type=int, choices=[1], default=1, help='1: 餐饮')
update_bu_parser.add_argument('longitude', required=False, type=str, help='经度')
update_bu_parser.add_argument('latitude', required=False, type=str, help='纬度')
update_bu_parser.add_argument('franchisee_id', required=False, type=str, help='加盟商ID， 由注册页面参数带入，餐饮店注册提交时一并提交')
update_bu_parser.add_argument('status', required=False, type=int, choices=[0, 1],
                              help='默认0，下架（页面不可见）；1，直接上架（页面需要提示用户，“请确认已上传店铺装修图片及产品信息”）')
update_bu_parser.add_argument('decorate_images', type=list, required=False, help='店铺装修图片', location='json')

bu_employees_page_parser = page_parser.copy()

new_bu_employee = reqparse.RequestParser()
new_bu_employee.add_argument('name', required=True, help='员工姓名')
new_bu_employee.add_argument('job_desc', required=True, choices=[1, 2, 3], help='1: boss, 2: leader, 3: waiter')

employee_bind_appid = reqparse.RequestParser()
employee_bind_appid.add_argument('age', required=False, help='年龄')
employee_bind_appid.add_argument('phone', required=True, help='用户扫描绑定入口，填写手机号验证')


@bu_ns.route('')
class BusinessUnitsAPI(Resource):
    @bu_ns.marshal_with(return_json)
    @bu_ns.expect(bu_page_parser)
    @permission_required([Permission.FRANCHISEE_MANAGER, "app.business_unit.BusinessUnitsAPI.get"])
    def get(self, **kwargs):
        """
        获取所有店铺
        """
        args = bu_page_parser.parse_args()
        if 'search' not in args.keys():
            args['search'] = {}
        args['search'] = {"name": args['name']}
        return success_return(get_table_data(BusinessUnits, args, appends=["decorate_images", "products"]), "请求成功")

    @bu_ns.doc(body=create_bu_parser)
    @bu_ns.marshal_with(return_json)
    @permission_required([Permission.FRANCHISEE_OPERATOR, "app.franchisee.FranchiseeAPI.post"])
    def post(self, **kwargs):
        """
        新增店铺
        """
        args = create_bu_parser.parse_args()
        check_name = BusinessUnits.query.filter(BusinessUnits.name.__eq__(args['name']),
                                                BusinessUnits.status.__eq__(1),
                                                BusinessUnits.delete_at.__eq__(None)).first()
        if check_name and not check_name.delete_at and geo_distance((check_name.latitude, check_name.longitude),
                                                                    (args['latitude'], args['longitude'])) <= 100:
            return false_return(message="100米内商铺名字重复")
        new_bu = new_data_obj("BusinessUnits",
                              **{"name": args['name'],
                                 "chain_store_code": args['chain_store_code'],
                                 "phone1": args['phone1'],
                                 "phone2": args['phone2'],
                                 "address": args['address'],
                                 "unit_type": args['unit_type'],
                                 "latitude": args['latitude'],
                                 "franchisee_id": args['franchisee_id'],
                                 "longitude": args['longitude']})

        if not new_bu or (new_bu and not new_bu['status']):
            return false_return(message="failed to create new business unit")

        else:
            append_image = image_operate.operate(new_bu['obj'], args['objects'], "append")
            if append_image.get("code") == 'success':
                return submit_return(f"店铺 {args['name']} 添加到成功，id：{new_bu['obj'].id}",
                                     f"店铺 {args['name']} 添加失败，因为图片追加失败")
            else:
                return false_return("图片添加失败")


@bu_ns.route('/<string:bu_id>')
@bu_ns.param('business unit', 'BUSINESS UNIT ID')
@bu_ns.expect(head_parser)
class PerBUApi(Resource):
    @bu_ns.marshal_with(return_json)
    @permission_required([Permission.BU_OPERATOR, "app.business_units.PerBUApi.get"])
    def get(self, **kwargs):
        """
        获取指定BU数据
        """
        return success_return(
            get_table_data_by_id(BusinessUnits, kwargs['bu_id'], ['bu_products']))

    @bu_ns.doc(body=update_bu_parser)
    @bu_ns.marshal_with(return_json)
    @permission_required([Permission.BU_OPERATOR, "app.business_units.PerBUApi.put"])
    def put(self, **kwargs):
        """更新BU"""
        args = update_bu_parser.parse_args()
        bu = BusinessUnits.query.get(kwargs['bu_id'])
        for k, v in args.items():
            if k == 'decorated_images':
                image_operate.operate(bu, None, None)
                image_operate.operate(obj=bu, imgs=args[k], action="append")
                continue

            check_bu = BusinessUnits.query.filter(BusinessUnits.id.__eq__(args['bu_id']),
                                                  BusinessUnits.name.__eq__(args['name']),
                                                  BusinessUnits.status.__eq__(1),
                                                  BusinessUnits.delete_at.__eq__(None)).first()
            if k == 'name' and check_bu and geo_distance((check_bu.latitude, check_bu.longitude),
                                                         (bu.latitude, bu.longitude)) <= 100:
                return false_return(message=f"<100米内存在{args['name']}>已经存在"), 400

            if hasattr(bu, k) and v:
                setattr(bu, k, v)

        return submit_return(f"SKU更新成功{args.keys()}", f"SKU更新失败{args.keys()}")

    @bu_ns.marshal_with(return_json)
    @permission_required("app.business_units.PerBUApi.delete")
    def delete(self, **kwargs):
        """删除"""
        bu = BusinessUnits.query.get(kwargs['bu_id'])
        if bu:
            bu.status = 0
            bu.delete_at = datetime.datetime.now()
            return submit_return("删除店铺成功", "删除店铺失败")
        else:
            return false_return(message=f"<{kwargs['sku_id']}>不存在"), 400


@bu_ns.route('/<string:bu_id>/employee')
@bu_ns.param('business unit', 'BUSINESS UNIT ID')
@bu_ns.expect(head_parser)
class BUEmployeesApi(Resource):
    @bu_ns.marshal_with(return_json)
    @permission_required([Permission.BU_OPERATOR, "app.business_units.PerBUApi.get"])
    def get(self, **kwargs):
        """
        获取店铺所属员工
        """
        args = bu_employees_page_parser.parse_args()
        args['search']['business_unit_id'] = kwargs['bu_id']
        return success_return(data=get_table_data(BusinessUnitEmployees, args))

    @bu_ns.doc(body=new_bu_employee)
    @bu_ns.marshal_with(return_json)
    @permission_required([Permission.BU_OPERATOR, "app.business_units.PerBUApi.put"])
    def post(self, **kwargs):
        args = new_bu_employee.parse_args()
        for k, v in args.items():
            # 目前不允许店铺内重名
            new_employee = new_data_obj("BusinessUnitEmployees", **{"name": args['name'],
                                                                    "job_desc": args['job_desc'],
                                                                    "business_unit_id": args['bu_id']})
            if not new_bu_employee or (new_bu_employee and not new_employee['status']):
                return false_return(message=f"create user {v} fail")
            return submit_return("create employee success", "create employee fail")


@bu_ns.route('/<string:bu_id>/employee/<string:employee_id>/bind')
@bu_ns.expect(head_parser)
class BUEmployeeBindAppID(Resource):
    @bu_ns.marshal_with(return_json)
    @permission_required([Permission.USER, "app.business_units.BUEmployeeBindAppID.put"])
    def get(self, **kwargs):
        """绑定入口进入时，获取员工信息"""
        return success_return(get_table_data_by_id(BusinessUnitEmployees,
                                                   kwargs['employee_id'],
                                                   appends=['bu_name', 'job_name'],
                                                   removes=['age', 'phone', 'phone_validated', 'customer_id']))

    @bu_ns.doc(body=employee_bind_appid)
    @bu_ns.marshal_with(return_json)
    @permission_required([Permission.USER, "app.business_units.BUEmployeeBindAppID.put"])
    def put(self, **kwargs):
        """
        绑定员工账号和微信APPID，前端页面先验证手机号，stage传bu_employee
        """
        args = employee_bind_appid.parse_args()
        current_user = kwargs.get('current_user')
        bu_employee = BusinessUnitEmployees.query.filter(BusinessUnitEmployees.id.__eq__(kwargs['employee_id']),
                                                         BusinessUnitEmployees.business_unit_id.__eq__(
                                                             kwargs['bu_id'])).first()
        bu_employee.customer_id = current_user.id
        bu_employee.phone = args['phone']
        bu_employee.phone_validated = True
        bu_employee.age = args['age']
        return submit_return("绑定成功", "绑定失败")

    @bu_ns.marshal_with(return_json)
    @permission_required([Permission.USER, "app.business_units.BUEmployeeBindAppID.delete"])
    def delete(self, **kwargs):
        pass
