from flask_restplus import Resource, reqparse, cors
from flask import request
from ..models import Permission, BusinessUnits, BusinessPurchaseOrders, BusinessUnitEmployees, BusinessUnitProducts, \
    Roles, BusinessUnitInventory, CustomerRoles, Customers, ShopOrders
from . import business_units
from .. import db, redis_db, default_api, logger, image_operate
from ..common import success_return, false_return, session_commit, sort_by_order, code_return, submit_return
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id, geo_distance, get_nearby, \
    _make_data, _advance_search
from ..decorators import permission_required, allow_cross_domain
from ..swagger import return_dict, head_parser, page_parser
import datetime
from sqlalchemy import and_

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
create_bu_parser.add_argument('longitude', required=True, type=float, help='经度')
create_bu_parser.add_argument('latitude', required=True, type=float, help='纬度')
create_bu_parser.add_argument('status', required=True, type=int, default=0, choices=[0, 1],
                              help='默认0，下架（页面不可见）；1，直接上架（页面需要提示用户，“请确认已上传店铺装修图片及产品信息”）')
create_bu_parser.add_argument('objects', type=list, required=False, help='店铺装修图片', location='json')

update_bu_parser = create_bu_parser.copy()
update_bu_parser.replace_argument('name', required=False, help='店铺名称（64）')
update_bu_parser.replace_argument('desc', required=False, type=str, help='店铺描述（200）')
update_bu_parser.replace_argument('phone1', required=False, type=str, help='电话1')
update_bu_parser.replace_argument('address', required=False, type=str, help='地址，手工输入')
update_bu_parser.replace_argument('unit_type', required=False, type=int, choices=[1], default=1, help='1: 餐饮')
update_bu_parser.replace_argument('longitude', required=False, type=str, help='经度')
update_bu_parser.replace_argument('latitude', required=False, type=str, help='纬度')
update_bu_parser.replace_argument('status', required=False, type=int, choices=[0, 1],
                                  help='默认0，下架（页面不可见）；1，直接上架（页面需要提示用户，“请确认已上传店铺装修图片及产品信息”）')
update_bu_parser.add_argument('bu_id', required=False, location='args', help='如果传递则按照bu id来查询，否则从用户反查其对应的BU ID')

bu_employees_page_parser = page_parser.copy()

new_bu_employee = reqparse.RequestParser()
new_bu_employee.add_argument('name', required=True, help='员工姓名')
new_bu_employee.add_argument('job_desc', required=True, help='1: boss, 2: leader, 3: waiter')

update_employee_parser = reqparse.RequestParser()
update_employee_parser.add_argument('name', required=False, help='员工姓名')
update_employee_parser.add_argument('job_desc', required=False, help='店铺员工，传入BU_MANAGER, BU_OPERATOR, BU_WAITER')
update_employee_parser.add_argument('age', required=False, help='年龄')
update_employee_parser.add_argument('phone', required=False, help='用户扫描绑定入口，填写手机号验证')

bu_nearby = reqparse.RequestParser()
bu_nearby.add_argument('distance', required=True, type=int, help='离当前坐标的距离', location='args')
bu_nearby.add_argument('longitude', required=True, type=str, help='经度', location='args')
bu_nearby.add_argument('latitude', required=True, type=str, help='纬度', location='args')
bu_nearby.add_argument('closest', required=True, type=int, help='0:全部，1:最近', location='args')

bu_detail_page_parser = page_parser.copy()
bu_detail_page_parser.add_argument('Authorization', required=True, location='headers')
bu_detail_page_parser.add_argument('bu_id', required=False, location='args', help='如果传递则按照bu id来查询，否则从用户反查其对应的BU ID')

inventory_search_parser = bu_detail_page_parser.copy()
inventory_search_parser.add_argument('sku_id', required=False, type=str, help='需要搜索的sku id', location='args')

dispatch_confirm_parser = reqparse.RequestParser()
dispatch_confirm_parser.add_argument('status', required=True, type=int, help='0,已发货未确认；1， 已发货已确认；2， 已发货未收到')
dispatch_confirm_parser.add_argument('memo', required=False, type=str, help='未启用，后续考虑用来添加备注')

get_bu_by_id = reqparse.RequestParser()
get_bu_by_id.add_argument('bu_id', required=False, location='args', help='如果传递则按照bu id来查询，否则从用户反查其对应的BU ID')

create_bu_product_parser = reqparse.RequestParser()
create_bu_product_parser.add_argument('name', required=True, type=str, help='产品名称（10）')
create_bu_product_parser.add_argument('desc', required=False, type=str, help='产品描述（50）')
create_bu_product_parser.add_argument('price', required=True, type=str, help='产品价格')
create_bu_product_parser.add_argument('objects', required=True, type=list, help='产品图片', location='json')
create_bu_product_parser.add_argument('order', required=False, type=int, help='产品排序, 不传为0')

update_bu_product_parser = create_bu_product_parser.copy()
update_bu_product_parser.replace_argument('name', required=False, type=str)
update_bu_product_parser.replace_argument('price', required=False, type=str)
update_bu_product_parser.replace_argument('objects', required=False, type=list, help='产品图片', location='json')

dispatch_parser = page_parser.copy()
dispatch_parser.add_argument("status", required=False, type=int, help='0: 已发货未确认，1：已发货已确认, 2:已发货未收到', location='args')
dispatch_parser.add_argument('operator', required=False, help='操作人员的ID', location='args')
dispatch_parser.add_argument('operate_at', type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d'),
                             help="操作日期，格式'%Y-%m-%d", location='args')

sold_parser = page_parser.copy()
sold_parser.add_argument("start_date", required=False, type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d'),
                         help="开始日期，格式'%Y-%m-%d", location='args')
sold_parser.add_argument("end_date", required=False, type=lambda x: datetime.datetime.strptime(x, '%Y-%m-%d'),
                         help="结束日期，格式'%Y-%m-%d", location='args')

sold_parser.add_argument("sku_id", required=False, help='sku id. 用于针对某种酒统计销售情况', location='args')
sold_parser.add_argument("bu_employee_id", required=False,
                         help='如果没传，根据用户id来查询，如果传了则按照员工ID来查询。如果员工是waiter，只能看到自己的卖酒统计，如果是店长则看到本店的，如果是老板，则能看到所有店（如果有连锁）')
sold_parser.add_argument('bu_id', required=False, location='args', help='如果传递则按照bu id来查询，否则从用户反查其对应的BU ID')


@bu_ns.route('')
@bu_ns.expect(head_parser)
class BusinessUnitsAPI(Resource):
    @bu_ns.marshal_with(return_json)
    @bu_ns.expect(bu_page_parser)
    @permission_required([Permission.FRANCHISEE_MANAGER, "app.business_unit.BusinessUnitsAPI.get"])
    def get(self, **kwargs):
        """
        获取所有店铺
        """
        args = bu_page_parser.parse_args()
        if args.get('name'):
            args['search'] = {"name": args['name']}
        return success_return(get_table_data(BusinessUnits, args, appends=['objects']), "请求成功")

    @bu_ns.doc(body=create_bu_parser)
    @bu_ns.marshal_with(return_json)
    @permission_required([Permission.FRANCHISEE_OPERATOR, "app.franchisee.FranchiseeAPI.post"])
    def post(self, **kwargs):
        """
        新增店铺,返回新增的店铺ID
        """
        try:
            args = create_bu_parser.parse_args()
            current_user = kwargs['current_user']
            franchisee_id = current_user.franchisee_operator.franchisee_id
            check_name = BusinessUnits.query.filter(BusinessUnits.name.__eq__(args['name']),
                                                    BusinessUnits.status.__eq__(1),
                                                    BusinessUnits.delete_at.__eq__(None)).first()
            if check_name and not check_name.delete_at and geo_distance((check_name.latitude, check_name.longitude),
                                                                        (args['latitude'], args['longitude'])) <= 100:
                raise Exception("100米内商铺名字重复")
            new_bu = new_data_obj("BusinessUnits",
                                  **{"name": args['name'],
                                     "desc": args['desc'],
                                     "chain_store_code": args.get('chain_store_code'),
                                     "phone1": args['phone1'],
                                     "phone2": args.get('phone2'),
                                     "address": args['address'],
                                     "unit_type": args.get('unit_type'),
                                     "latitude": args['latitude'],
                                     "franchisee_id": franchisee_id,
                                     "longitude": args['longitude']})

            if not new_bu or (new_bu and not new_bu['status']):
                raise Exception("failed to create new business unit")
            else:
                if args.get('objects'):
                    append_image = image_operate.operate(new_bu['obj'], args['objects'], "append")
                else:
                    append_image = {'code': 'success'}

                if append_image.get("code") == 'success' and session_commit().get('code') == 'success':
                    # invitation_code = generate_code(12)
                    # redis_db.set(invitation_code, new_bu['obj'].id)
                    # redis_db.expire(invitation_code, 600)
                    # return success_return(data={'scene': 'new_bu', 'scene_invitation': invitation_code})
                    return success_return(data={'new_bu': new_bu['obj'].id})
                elif append_image.get("code") == 'false':
                    raise Exception("图片添加失败")
                else:
                    raise Exception("新增店铺失败")
        except Exception as e:
            return false_return(message=str(e)), 400


@bu_ns.route('/products')
@bu_ns.expect(head_parser)
class BUProductsApi(Resource):
    @bu_ns.doc(body=bu_detail_page_parser)
    @bu_ns.marshal_with(return_json)
    @permission_required(Permission.BU_OPERATOR)
    def get(self, **kwargs):
        """获取指定BU的商品列表"""
        args = bu_detail_page_parser.parse_args()
        if args.get('bu_id'):
            bu_id = args['bu_id']
        else:
            bu_id = kwargs['current_user'].business_unit_employee.business_unit_id
        args['search'] = {'bu_id': bu_id, "delete_at": None}
        return success_return(data=get_table_data(BusinessUnitProducts, args, appends=['objects']))

    @bu_ns.doc(body=create_bu_product_parser)
    @bu_ns.marshal_with(return_json)
    @permission_required([Permission.BU_OPERATOR, "app.franchisee.FranchiseeAPI.post"])
    def post(self, **kwargs):
        """
        新增店铺商品，返回新增的商品ID
        """
        args = create_bu_product_parser.parse_args()
        if args.get('bu_id'):
            bu_id = args['bu_id']
        else:
            bu_id = kwargs['current_user'].business_unit_employee.business_unit_id
        if BusinessUnitProducts.query.filter_by(name=args.get('name')).first():
            return false_return(message="店铺产品名重复")
        new_product = new_data_obj("BusinessUnitProducts", **{"name": args.get('name'),
                                                              "desc": args.get('desc'),
                                                              "price": args.get('price'),
                                                              "bu_id": bu_id,
                                                              "order": args.get('order')})
        if not new_product or (new_product and not new_product['status']):
            return false_return(message="店铺产品名已存在")

        if args.get("objects"):
            append_image = image_operate.operate(obj=new_product['obj'], imgs=args["objects"], action="append")
            if append_image.get("code") == 'success':
                return submit_return("产品添加成功", "产品添加失败")
            else:
                return false_return("图片添加失败")
        else:
            return submit_return("产品添加成功", "产品添加失败")


@bu_ns.route('/product/<string:bu_product_id>')
@bu_ns.param('bu_product_id', '店铺产品ID')
@bu_ns.expect(head_parser)
class BUPerProductsApi(Resource):
    @bu_ns.marshal_with(return_json)
    @permission_required([Permission.BU_OPERATOR, "app.franchisee.FranchiseeAPI.post"])
    def get(self, **kwargs):
        """获取店铺产品"""
        return success_return(
            data=get_table_data_by_id(BusinessUnitProducts,
                                      kwargs['bu_product_id'],
                                      appends=['objects'],
                                      search={'delete_at': None}))

    @bu_ns.doc(body=update_bu_product_parser)
    @bu_ns.marshal_with(return_json)
    @permission_required([Permission.BU_OPERATOR, "app.franchisee.FranchiseeAPI.post"])
    def put(self, **kwargs):
        """
        修改店铺商品
        """
        args = update_bu_product_parser.parse_args()
        if args.get('bu_id'):
            bu_id = args['bu_id']
        else:
            bu_id = kwargs['current_user'].business_unit_employee.business_unit_id

        bu_product = BusinessUnitProducts.query.filter(BusinessUnitProducts.id == kwargs['bu_product_id'],
                                                       BusinessUnitProducts.bu_id == bu_id,
                                                       BusinessUnitProducts.delete_at.__eq__(None)).first()

        for k, v in args.items():
            if k == 'objects':
                image_operate.operate(bu_product, None, None)
                image_operate.operate(obj=bu_product, imgs=args[k], action="append")
                continue

            if hasattr(bu_product, k) and v:
                setattr(bu_product, k, v)

        return submit_return(f"BU PRODUCT更新成功{args.keys()}", f"SKU更新失败{args.keys()}")

    @bu_ns.marshal_with(return_json)
    @permission_required([Permission.BU_OPERATOR, "app.franchisee.FranchiseeAPI.post"])
    def delete(self, **kwargs):
        """删除产品"""
        bu_id = kwargs['current_user'].business_unit_employee.business_unit_id
        bu_product = BusinessUnitProducts.query.filter_by(id=kwargs['bu_product_id'], bu_id=bu_id).first()
        bu_product.delete_at = datetime.datetime.now()
        return submit_return(f"删除成功", f"删除失败")


@bu_ns.route('/inventory')
@bu_ns.expect(head_parser)
class BUInventoryApi(Resource):
    @bu_ns.doc(body=bu_detail_page_parser)
    @bu_ns.marshal_with(return_json)
    @permission_required(Permission.BU_OPERATOR)
    def get(self, **kwargs):
        """获取指定BU的库存量"""
        args = inventory_search_parser.parse_args()
        if args.get('bu_id'):
            bu_id = args['bu_id']
        else:
            bu_id = kwargs['current_user'].business_unit_employee.business_unit_id

        if args.get('sku_id'):
            args['search'] = {'sku_id': args.pop('sku_id'), 'franchisee_id': bu_id}
        else:
            args['search'] = {'franchisee_id': bu_id}
        return success_return(data=get_table_data(BusinessUnitInventory, args, appends=['sku']))


@bu_ns.route('/per_bu')
@bu_ns.expect(head_parser)
class PerBUApi(Resource):
    @bu_ns.doc(body=get_bu_by_id)
    @bu_ns.marshal_with(return_json)
    @permission_required([Permission.BU_OPERATOR, "app.business_units.PerBUApi.get"])
    def get(self, **kwargs):
        """获取指定BU详情"""
        args = get_bu_by_id.parse_args()
        if args.get('bu_id'):
            bu_id = args['bu_id']
        else:
            bu_id = kwargs['current_user'].business_unit_employee.business_unit_id
        return success_return(get_table_data_by_id(BusinessUnits, bu_id, appends=['objects']))

    @bu_ns.doc(body=update_bu_parser)
    @bu_ns.marshal_with(return_json)
    @permission_required([Permission.BU_OPERATOR, "app.business_units.PerBUApi.put"])
    def put(self, **kwargs):
        """更新BU"""
        args = update_bu_parser.parse_args()
        if args.get('bu_id'):
            bu = BusinessUnits.query.get(args['bu_id'])
        else:
            bu = kwargs['current_user'].business_unit_employee.business_unit
        for k, v in args.items():
            if k == 'objects':
                image_operate.operate(bu, None, None)
                image_operate.operate(obj=bu, imgs=args[k], action="append")
                continue

            if k == 'name':
                check_bu = BusinessUnits.query.filter(BusinessUnits.id.__eq__(bu.id),
                                                      BusinessUnits.name.__eq__(args['name']),
                                                      BusinessUnits.status.__eq__(1),
                                                      BusinessUnits.delete_at.__eq__(None)).first()
                if check_bu and geo_distance((check_bu.latitude, check_bu.longitude),
                                             (bu.latitude, bu.longitude)) <= 100:
                    return false_return(message=f"<100米内存在{args['name']}>已经存在"), 400

            if hasattr(bu, k) and v:
                setattr(bu, k, v)

        return submit_return(f"BU更新成功{args.keys()}", f"SKU更新失败{args.keys()}")

    # @bu_ns.marshal_with(return_json)
    # @permission_required(Permission.BU_MANAGER)
    # def delete(self, **kwargs):
    #     """删除"""
    #     bu = kwargs['current_user'].business_unit_employee.business_unit
    #     if bu:
    #         bu.status = 0
    #         bu.delete_at = datetime.datetime.now()
    #         return submit_return("删除店铺成功", "删除店铺失败")
    #     else:
    #         return false_return(message=f"<{kwargs['sku_id']}>不存在"), 400


@bu_ns.route('/employee')
@bu_ns.expect(head_parser)
class BUEmployeesApi(Resource):
    @bu_ns.marshal_with(return_json)
    @permission_required(Permission.BU_OPERATOR)
    def get(self, **kwargs):
        """
        获取店铺所属员工
        """
        args = bu_employees_page_parser.parse_args()
        if args.get('bu_id'):
            bu_id = args['bu_id']
        else:
            bu_id = kwargs['current_user'].business_unit_employee.business_unit_id
        args['search'] = {'business_unit_id': bu_id, 'delete_at': None}
        return success_return(data=get_table_data(BusinessUnitEmployees, args, appends=['job_name']))

    @bu_ns.doc(body=new_bu_employee)
    @bu_ns.marshal_with(return_json)
    @permission_required(Permission.BU_OPERATOR)
    def post(self, **kwargs):
        """新增员工"""
        args = new_bu_employee.parse_args()
        if args.get('bu_id'):
            bu_id = args['bu_id']
        else:
            bu_id = kwargs['current_user'].business_unit_employee.business_unit_id

        # 店铺经理和店长在一个店铺中唯一
        role_name = CustomerRoles.query.get(args['job_desc']).name
        if role_name in ("BU_OPERATOR", "BU_MANAGER"):
            tmp_obj = BusinessUnitEmployees.query.filter(BusinessUnitEmployees.business_unit_id.__eq__(bu_id),
                                                         BusinessUnitEmployees.job_desc.__eq__(args['job_desc'])).all()
            if tmp_obj:
                return false_return(message="当前角色唯一，不可添加"), 400

        new_employee = new_data_obj("BusinessUnitEmployees", **{"name": args['name'],
                                                                "job_desc": args['job_desc'],
                                                                "business_unit_id": bu_id})
        if not new_employee or (new_employee and not new_employee['status']):
            return false_return(message=f"create user {args['name']} fail")
        else:
            if session_commit().get("code") == 'success':
                return success_return(data={'new_bu_employee': new_employee['obj'].id})
            else:
                return false_return(message="create employee fail"), 400


@bu_ns.route('/employee/<string:employee_id>')
@bu_ns.expect(head_parser)
class PerBUEmployee(Resource):
    @bu_ns.marshal_with(return_json)
    @permission_required(Permission.BU_OPERATOR)
    def get(self, **kwargs):
        """获取指定员工的详情"""
        return success_return(
            data=get_table_data_by_id(BusinessUnitEmployees,
                                      kwargs['employee_id'],
                                      appends=['job_name'],
                                      removes=['job_desc'],
                                      search={'delete_at': None}))

    @bu_ns.doc(body=update_employee_parser)
    @bu_ns.marshal_with(return_json)
    @permission_required(Permission.BU_WAITER)
    def put(self, **kwargs):
        """修改员工账号信息"""
        args = update_employee_parser.parse_args()
        current_user = kwargs.get('current_user')
        bu_id = current_user.business_unit_employee.business_unit_id
        bu_employee = BusinessUnitEmployees.query.filter(BusinessUnitEmployees.id.__eq__(kwargs['employee_id']),
                                                         BusinessUnitEmployees.business_unit_id.__eq__(bu_id)).first()
        for k, v in args.items():
            if k == 'job_desc' and v in ("BU_MANAGER", "BU_OPERATOR", "BU_WAITER"):
                role_obj = CustomerRoles.query.filter_by(name=v).first()
                if not role_obj:
                    return false_return(message="角色不存在"), 400
                bu_employee.role = role_obj

            elif hasattr(bu_employee, k):
                setattr(bu_employee, k, v)
            else:
                return false_return(message="角色属性不存在"), 400
        return submit_return("修改成功", "修改失败")

    @bu_ns.marshal_with(return_json)
    @permission_required(Permission.BU_OPERATOR)
    def delete(self, **kwargs):
        employee_obj = BusinessUnitEmployees.query.get(kwargs['employee_id'])
        employee_obj.delete_at = datetime.datetime.now()
        return submit_return("delete successful", "delete failed")


@bu_ns.route('/nearby')
@bu_ns.expect(head_parser)
class BUNearby(Resource):
    @bu_ns.doc(body=bu_nearby)
    @bu_ns.marshal_with(return_json)
    @permission_required([Permission.USER, "app.business_units.BUNearby.post"])
    def get(self, **kwargs):
        """附近的店铺。若需要查找距离最近的店铺， distance传1000， closest传1"""
        try:
            import math
            args = bu_nearby.parse_args()
            distance = args['distance']
            longitude = eval(args['longitude'])
            latitude = eval(args['latitude'])

            # 获取距离是distance内的坐标范围，用左上，左下，右上，右下四个坐标来圈定范围
            nearby_range = get_nearby(latitude, longitude, distance * 0.001)

            # 查表，获取符合范围内的店铺
            nearby_objs = [
                {"obj": get_table_data_by_id(BusinessUnits, obj.id, appends=['objects'], search={'delete_at': None}),
                 "distance": math.ceil(geo_distance((latitude, longitude), (obj.latitude, obj.longitude)))} for
                obj in BusinessUnits.query.filter(
                    BusinessUnits.latitude.between(nearby_range['south'].latitude, nearby_range['north'].latitude),
                    BusinessUnits.longitude.between(nearby_range['west'].longitude, nearby_range['east'].longitude)
                ).all()]

            # 按照距离排序
            nearby_objs.sort(key=lambda x: x['distance'])
            if args['closest'] == 0:
                return success_return(data=nearby_objs)
            else:
                return success_return(data=nearby_objs[0] if nearby_objs else None)
        except Exception as e:
            return false_return(message=str(e)), 400


@bu_ns.route('/purchase_orders')
@bu_ns.expect(head_parser)
class BUPurchaseOrdersAPI(Resource):
    @bu_ns.doc(body=dispatch_parser)
    @bu_ns.marshal_with(return_json)
    @permission_required(Permission.BU_OPERATOR)
    def get(self, **kwargs):
        """获取所有入库单"""
        args = dispatch_parser.parse_args()
        args['search'] = dict()
        for k, v in args.items():
            if k in ('status', 'operator', 'operate_at') and v:
                args['search'][k] = v
        args['search']['delete_at'] = None
        return success_return(data=get_table_data(BusinessPurchaseOrders, args, appends=['original_order', 'sku']))


@bu_ns.route('/purchase_orders/<string:bu_purchase_order_id>')
@bu_ns.param('bu_purchase_order_id', '货单ID')
@bu_ns.expect(head_parser)
class BUPurchaseOrdersAPI(Resource):
    @bu_ns.marshal_with(return_json)
    @permission_required(Permission.BU_OPERATOR)
    def get(self, **kwargs):
        """获取指定入库单"""
        return success_return(
            data=get_table_data_by_id(BusinessPurchaseOrders, kwargs['bu_purchase_order_id'],
                                      search={'delete_at': None}, appends=['original_order']))

    @bu_ns.doc(body=dispatch_confirm_parser)
    @bu_ns.marshal_with(return_json)
    @permission_required(Permission.BU_OPERATOR)
    def put(self, **kwargs):
        """修改入库记录状态，如果修改为已收货并确认，则将入库单货物计入库存量中"""
        args = dispatch_confirm_parser.parse_args()
        status = args['status']
        current_user = kwargs.get('current_user')
        if not current_user.franchisee_operator:
            return false_return(message="当前用户无加盟商角色")

        bu_id = kwargs['current_user'].business_unit_employee.business_unit_id
        bpo_obj = BusinessPurchaseOrders.query.get(kwargs['bu_purchase_order_id'])
        # 创建sku的库存，如果存在则返回对应的记录，如果不存在则新建
        bi_obj = new_data_obj("BusinessUnitInventory",
                              **{"sku_id": bpo_obj.sku_id,
                                 "bu_id": bu_id})

        if not bi_obj:
            return false_return(message="获取店铺存失败")

        if bpo_obj.status in (1, 2) or bpo_obj.delete_at is not None:
            return false_return(message="该货单状态异常不可确认")

        if status == 1:
            bpo_obj.status = status
            bpo_obj.original_order.dispatch_status = status
            bi_obj['obj'].amount += bpo_obj.amount

        return submit_return("确认成功", "确认失败")


@bu_ns.route('/statistics/<string:scene>')
@bu_ns.param('scene', "pickup或者sold。Pickup指取酒的统计。sold指卖掉的酒且是消费者首单的酒")
@bu_ns.expect(head_parser)
class BUStatistics(Resource):
    @bu_ns.marshal_with(return_json)
    @bu_ns.doc(body=sold_parser)
    @permission_required(Permission.BU_WAITER)
    def get(self, **kwargs):
        """店铺卖掉的酒"""
        args = sold_parser.parse_args()

        advance_search = list()
        args['search'] = dict()

        if args.get('bu_id'):
            bu_id = args['bu_id']
        else:
            bu_id = kwargs['current_user'].business_unit_employee.business_unit_id

        if args.get('bu_employee_id'):
            bu_employee = BusinessUnitEmployees.query.get(args['bu_employee_id'])
        else:
            bu_employee = kwargs['current_user'].business_unit_employee

        waiter_role_id = CustomerRoles.query.filter(CustomerRoles.name.__eq__('BU_WAITER')).first().id
        if bu_employee.job_desc == waiter_role_id:
            args['search']['operator'] = bu_employee.id

        if args.get('start_date'):
            advance_search.append({"key": "create_at", "operator": "__ge__", "value": args.get('start_date')})
        if args.get('end_date'):
            advance_search.append({"key": "create_at", "operator": "__le__", "value": args.get('end_date')})
        if args.get('status'):
            args['search']['status'] = args.get('status')
        if args.get('sku_id'):
            args['search']['sku_id'] = args.get('sku_id')

        if kwargs['scene'] == 'pickup':
            advance_search.append({"key": "amount", "operator": "__lt__", "value": 0})
            args['search']['bu_id'] = bu_id
            return success_return(
                data=get_table_data(BusinessPurchaseOrders, args, advance_search=advance_search, order_by="operate_at"))
        elif kwargs['scene'] == 'sold':
            consumers = kwargs['current_user'].business_unit_employee.consumers.filter(
                Customers.first_order_id.__ne__(None)).all()
            orders = list()
            fields = table_fields(ShopOrders)
            for c in consumers:
                if advance_search:
                    and_filter = _advance_search(table=ShopOrders, advance_search=advance_search)
                    and_filter.append(ShopOrders.id.__eq__(c.first_order_id))
                    order_obj = ShopOrders.query.filter(and_(*and_filter)).first()
                    if order_obj:
                        orders.append(order_obj)
                else:
                    orders.append(ShopOrders.query.get(c.first_order_id))
            return success_return(data=_make_data(orders, fields))

