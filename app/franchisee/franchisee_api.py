from flask_restplus import Resource, reqparse, cors
from flask import request
from ..models import Permission, Franchisees, FranchiseeScopes, FranchiseeOperators, FranchiseePurchaseOrders
from . import franchisee
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, sort_by_order, code_return, submit_return
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id
from ..decorators import permission_required, allow_cross_domain
from ..swagger import return_dict, head_parser, page_parser

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

create_franchisee_scope = reqparse.RequestParser()
create_franchisee_scope.add_argument('province', required=True)
create_franchisee_scope.add_argument('city', required=True)
create_franchisee_scope.add_argument('district')
create_franchisee_scope.add_argument('street', help='街道')

put_scope = reqparse.RequestParser()
put_scope.add_argument('franchisee_id', required=True)


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

    # def post(self, **kwargs):
    #     """新增Banner"""
    #     args = add_banner_parser.parse_args()
    #     new_banner = new_data_obj("Banners",
    #                               **{"name": args['name'], "order": args['order'], "objects": args['object']})
    #     if new_banner:
    #         if new_banner.get('status'):
    #             return submit_return("新增banner成功", "新增banner失败")
    #         else:
    #             cos_client = QcloudCOS()
    #             cos_client.delete(ObjStorage.query.get(args['object']).obj_key)
    #             return false_return(message=f"<{args['name']}>已经存在"), 400
    #     else:
    #         cos_client = QcloudCOS()
    #         cos_client.delete(ObjStorage.query.get(args['object']).obj_key)
    #         return false_return(message="新增banner失败"), 400


@franchisee_ns.route('/scopes')
class FranchiseeScopesAPI(Resource):
    @franchisee_ns.marshal_with(return_json)
    @franchisee_ns.expect(franchisee_scopes_page_parser)
    @permission_required(Permission.ADMINISTER)
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
    @permission_required("app.franchisee.FranchiseeAPI.post")
    def post(self, **kwargs):
        """
        新增加盟商运营范围
        :param kwargs:
        :return:
        """
        args = create_franchisee_parser.parse_args()
        new_scope = new_data_obj("FranchiseeScopes",
                                 **{"province": args['province'],
                                    "city": args['city'],
                                    "district": args['district'],
                                    "street": args['street']})
        if new_scope:
            if new_scope.get('status'):
                return submit_return(f"新增运营范围成功", "新增运营范围失败")
            else:
                if not new_scope['obj']['franchisee_id']:
                    return submit_return(f"运营范围已存在，未绑定加盟商", "新增运营范围失败")
                else:
                    return false_return(message="新增范围失败"), 400
        else:
            return false_return(message="新增范围失败"), 400


@franchisee_ns.route('/scopes/<string:scope_id>/franchisee')
class FranchiseeScopeBindAPI(Resource):
    @franchisee_ns.doc(body=put_scope)
    @franchisee_ns.marshal_with(return_json)
    @permission_required(Permission.ADMINISTER)
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
    @permission_required(Permission.ADMINISTER)
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