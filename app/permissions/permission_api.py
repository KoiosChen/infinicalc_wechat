from flask import jsonify, request
from flask_restplus import Resource, fields, reqparse
from ..models import Users, Roles, Menu, Permissions, role_menu
from . import permissions
from app.auth import auths
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
from ..public_method import table_fields, new_data_obj
import datetime
from ..decorators import permission_required
from ..swagger import return_dict, head_parser
from sqlalchemy import or_

permission_ns = default_api.namespace('permissions', path='/permissions', description='包括权限相关操作')

return_json = permission_ns.model('ReturnRegister', return_dict)

permission_add_parser = reqparse.RequestParser()
permission_add_parser.add_argument('name', required=True, help='权限名称')
permission_add_parser.add_argument('action', required=True, help='权限标识')

permission_change_parser = reqparse.RequestParser()
permission_change_parser.add_argument('name', help='权限名称')
permission_change_parser.add_argument('action', help='权限标识')


@permission_ns.route('')
@permission_ns.expect(head_parser)
class QueryPermissions(Resource):
    @permission_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.query_permissions")
    def get(self, **kwargs):
        """
        获取全部权限
        """
        fields_ = table_fields(Permissions)
        r = [{f: getattr(p, f) for f in fields_} for p in Permissions.query.all()]
        return success_return(r, "")

    @permission_ns.doc(body=permission_add_parser)
    @permission_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.add_permission")
    def post(self, **kwargs):
        """创建权限"""
        args = permission_add_parser.parse_args()
        now_p = Permissions.query.filter_by(action=args['action']).first()
        if now_p:
            return false_return(message=f"<{args['action']}>已经存在，当前权限名为<{now_p.name}>")
        new_one = new_data_obj("Permissions", **{"name": args['name'], "action": args['action']})
        return success_return(message=f"{args['name']}: {args['action']} 添加成功，id：{new_one['obj'].id}")


@permission_ns.route('/<int:permission_id>')
@permission_ns.expect(head_parser)
class PermissionById(Resource):
    @permission_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.query_permission_by_id")
    def get(self, **kwargs):
        """
        获取特定权限
        """
        fields_ = table_fields(Permissions)
        p = Permissions.query.get(kwargs['permission_id'])
        r = {f: getattr(p, f) for f in fields_}
        return success_return(r, "")

    @permission_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.delete_permission_by_id")
    def delete(self, **kwargs):
        """删除权限"""
        p = Permissions.query.get(kwargs['permission_id'])
        if p:
            db.session.delete(p)
            return success_return() if session_commit() else false_return(message='权限删除时数据提交失败')
        else:
            return false_return(message=f'ID：{kwargs["permission_id"]}不存在')

    @permission_ns.doc(body=permission_change_parser)
    @permission_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.delete_permission_by_id")
    def put(self, **kwargs):
        """修改权限"""
        args = permission_change_parser.parse_args()
        if Permissions.query.filter(
                or_(Permissions.name.__eq__(args['name']), Permissions.action.__eq__(args['action']))).all():
            return false_return('权限修改失败，内容冲突')

        p = Permissions.query.get(kwargs['permission_id'])
        if p:
            if args['name']:
                p.name = args['name']
            if args['action']:
                p.action = args['action']
            return success_return()
        else:
            return false_return(f"ID {kwargs['permission_id']}不存在")
