from flask import jsonify, request
from flask_restplus import Resource, fields, reqparse
from ..models import Users, Roles, Menu, Permissions, role_menu
from . import users
from app.auth import auths
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
import datetime
from ..decorators import permission_required
from ..swagger import return_dict, head_parser

roles_ns = default_api.namespace('roles', path='/roles',
                                 description='包括角色、菜单、权限相关操作')

role_add_parser = reqparse.RequestParser()
role_add_parser.add_argument('name', required=True, help='新的角色名称', location='json')
role_add_parser.add_argument('menus', required=True, type=list, help='该角色可用的权限ID，list。例如，[1,3,4,5]', location='json')

role_bind_menu_parser = reqparse.RequestParser()
role_bind_menu_parser.add_argument('role_id', required=True, help='用户选择要操作的role的id', location='json')
role_bind_menu_parser.add_argument('menus', required=True, type=list,
                                   help='该角色可用的权限ID，list。例如，[1,3,4,5]，从/roles/query_menus获取',
                                   location='json')

role_delete_parser = reqparse.RequestParser()
role_delete_parser.add_argument('role_id', required=True, help='要删除的角色ID(Roles.id)')

role_change_parser = reqparse.RequestParser()
role_change_parser.add_argument('name', help='修改角色名称(Roles.name)')
role_change_parser.add_argument('menus', help='修改的菜单ID，dict前到list。{"add": [1,2], "delete": [3]}')

query_menu_parser = reqparse.RequestParser()
query_menu_parser.add_argument('role_id', help='要查询的角色ID(Roles.id)， 若此字段为空，则返回所有')

return_json = roles_ns.model('ReturnRegister', return_dict)


@roles_ns.route('/add_role')
@roles_ns.expect(head_parser)
class AddRole(Resource):
    @roles_ns.doc(body=role_add_parser)
    @roles_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.add_role")
    def post(self, info):
        """
        添加角色
        """
        args = role_add_parser.parse_args()
        menus_list = [Menu.query.get(m) for m in args['menus']]
        logger.debug(menus_list)
        if not Roles.query.filter_by(name=args['name']).first():
            new_role = Roles(name=args['name'])
            db.session.add(new_role)
            for menu_ in menus_list:
                new_role.menus.append(menu_)
            return success_return(data={"new_role_id": new_role.id},
                                  message="角色添加成功") \
                if session_commit() else false_return(message="角色添加失败")
        else:
            return false_return(message=f"{args['name']}已经存在")


@roles_ns.route('/role_bind_menu')
@roles_ns.expect(head_parser)
class RoleBindMenu(Resource):
    @roles_ns.doc(body=role_bind_menu_parser)
    @roles_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.role_bind_menu")
    def post(self, info):
        """
        将权限添加到指定角色下
        """
        args = role_bind_menu_parser.parse_args()
        role_ = Roles.query.get(args['role_id'])
        fail_add_menu_name = list()
        if role_:
            for menu_ in [Menu.query.get(m) for m in args['menus']]:
                if menu_ not in role_.menus:
                    role_.menus.append(menu_)
                else:
                    fail_add_menu_name.append(menu_.name)
            return success_return(
                message="权限添加到角色成功" if not fail_add_menu_name else f"权限添加部分成功，其中{fail_add_menu_name}已存在")
        else:
            return false_return(message="角色不存在")


@roles_ns.route('/role_unbind_menu')
@roles_ns.expect(head_parser)
class RoleUnbindMenu(Resource):
    @roles_ns.doc(body=role_bind_menu_parser)
    @roles_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.role_unbind_menu")
    def post(self, info):
        """
        删除角色中的权限
        """
        args = role_bind_menu_parser.parse_args()
        role_ = Roles.query.get(args['role_id'])
        fail_unbind_menu_name = list()
        if role_:
            for menu_ in [Menu.query.get(m) for m in args['menus']]:
                if menu_ in role_.menus:
                    role_.menus.remove(menu_)
                else:
                    fail_unbind_menu_name.append(menu_.name)
            return success_return(
                message="权限添加到角色成功" if not fail_unbind_menu_name else f"权限删除部分成功，其中{fail_unbind_menu_name}不存在")
        else:
            return false_return(message="角色不存在")


@roles_ns.route('/query_roles')
@roles_ns.expect(head_parser)
class QueryRoles(Resource):
    @roles_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.query_roles")
    def get(self, info):
        """
        获取指定范围的角色列表
        :return: json
        """
        role_field = Roles.__table__.columns.keys()
        role_field.append('menus')
        roles = Roles.query.all()
        return_roles = list()
        for role in roles:
            tmp = dict()
            for f in role_field:
                if f == 'menus':
                    tmp[f] = [m.name for m in role.menus]
                else:
                    tmp[f] = getattr(role, f)
            return_roles.append(tmp)
        print(return_roles)
        return success_return(return_roles, "请求成功")


@roles_ns.route('/query_menus')
@roles_ns.expect(head_parser)
class QueryMenus(Resource):
    @roles_ns.doc(body=query_menu_parser)
    @roles_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.query_menus")
    def get(self, info):
        """
        获取指定角色的权限列表
        :return: json
        """
        args = query_menu_parser.parse_args()
        role_id = args['role_id']
        menu_fields = Menu.__table__.columns.keys()
        menu_fields.append("permissions")
        if not role_id:
            menus = Menu.query.all()
        else:
            menus = Menu.query.outerjoin(role_menu).outerjoin(Roles).filter(Roles.id.__eq__(role_id)).all()
        return_menu = list()
        for menu in menus:
            tmp = dict()
            for f in menu_fields:
                if f == 'permissions':
                    tmp[f] = menu.permissions.action
                else:
                    tmp[f] = getattr(menu, f)
            return_menu.append(tmp)
        return success_return(return_menu, "请求成功")
