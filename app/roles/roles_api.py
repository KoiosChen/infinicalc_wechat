from flask import jsonify, request
from flask_restplus import Resource, fields, reqparse
from ..models import Users, Roles, Menu, Permissions, role_menu
from . import roles
from app.auth import auths
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
import datetime
from ..decorators import permission_required
from ..swagger import return_dict, head_parser
from ..menus.menus_api import get_menus

roles_ns = default_api.namespace('roles', path='/roles', description='包括角色、菜单、权限相关操作')

role_add_parser = reqparse.RequestParser()
role_add_parser.add_argument('name', required=True, help='新的角色名称', location='json')
role_add_parser.add_argument('menus', required=True, type=list, help='该角色可用的权限ID，list。例如，[1,3,4,5]', location='json')

role_change_parser = reqparse.RequestParser()
role_change_parser.add_argument('name', required=True, help='新的角色名称')

role_bind_menu_parser = reqparse.RequestParser()
role_bind_menu_parser.add_argument('menus', required=True, type=list,
                                   help='该角色可用的权限ID，list。例如，[1,3,4,5]，从/roles/query_menus获取',
                                   location='json')

role_delete_parser = reqparse.RequestParser()
role_delete_parser.add_argument('role_id', required=True, help='要删除的角色ID(Roles.id)')

role_change_parser = reqparse.RequestParser()
role_change_parser.add_argument('name', required=True, help='修改角色名称(Roles.name)')

query_menu_parser = reqparse.RequestParser()
query_menu_parser.add_argument('role_id', help='要查询的角色ID(Roles.id)， 若此字段为空，则返回所有')

return_json = roles_ns.model('ReturnRegister', return_dict)


def get_roles(role_id=None):
    role_field = Roles.__table__.columns.keys()
    role_field.append('menus')
    if role_id is None:
        roles = Roles.query.all()
    else:
        roles = [Roles.query.get(role_id)]
    return_roles = list()
    for role in roles:
        tmp = dict()
        for f in role_field:
            if f == 'menus':
                tmp[f] = {m.id: m.name for m in role.menus}
            else:
                tmp[f] = getattr(role, f)
        return_roles.append(tmp)
    return return_roles


@roles_ns.route('')
class RoleApi(Resource):
    @roles_ns.expect(head_parser)
    @roles_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.query_roles")
    def get(self, info):
        """
        获取所有角色列表
        """
        return success_return(get_roles(), "请求成功")

    @roles_ns.expect(head_parser)
    @roles_ns.doc(body=role_add_parser)
    @roles_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.add_roles")
    def post(self, info):
        """
        添加角色
        """
        args = role_add_parser.parse_args(strict=True)
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


@roles_ns.route("/<int:role_id>")
@roles_ns.expect(head_parser)
@roles_ns.param('role_id', 'the role id')
class RoleID(Resource):
    @roles_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.query_role")
    def get(self, **kwargs):
        return success_return(get_roles(kwargs['role_id']))

    @roles_ns.doc(body=role_change_parser)
    @roles_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.change_role")
    def put(self, **kwargs):
        """
        修改角色
        """
        args = role_change_parser.parse_args(strict=True)
        name_tobe = args['name']
        role_id = kwargs['role_id']
        role = Roles.query.get(role_id)
        if not Roles.query.filter_by(name=name_tobe).first():
            old_name = role.name
            role.name = name_tobe
            db.session.add(role)
            return success_return(message=f"角色修改成功{old_name}->{name_tobe}") if session_commit() else false_return(
                message="角色添加失败")
        else:
            return false_return(message=f"{name_tobe}已经存在")

    @roles_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.delete_role")
    def delete(self, **kwargs):
        pass


@roles_ns.route('/<int:role_id>/menus')
@roles_ns.expect(head_parser)
@roles_ns.param('role_id', 'the role id')
class RoleMenu(Resource):
    @roles_ns.doc(body=role_bind_menu_parser)
    @roles_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.bind_menu_by_role_id")
    def put(self, **kwargs):
        """
        修改制定角色（role_id）对应的权限列表
        """
        args = role_bind_menu_parser.parse_args()
        role_id = kwargs['role_id']
        role_ = Roles.query.get(role_id)
        fail_change_menu_name = list()
        now_menus = args['menus']
        menus_in_db = Menu.query.outerjoin(role_menu).outerjoin(Roles).filter(Roles.id.__eq__(role_id)).all()
        old_menus = [m.id for m in menus_in_db]
        menus_tobe_added = set(now_menus) - set(old_menus)
        menus_tobe_deleted = set(old_menus) - set(now_menus)
        if role_:
            for menu_ in [Menu.query.get(m) for m in menus_tobe_added]:
                if menu_ not in role_.menus:
                    role_.menus.append(menu_)
                else:
                    fail_change_menu_name.append(menu_.name)

            for menu_ in [Menu.query.get(m) for m in menus_tobe_deleted]:
                if menu_ in role_.menus:
                    role_.menus.remove(menu_)
                else:
                    fail_change_menu_name.append(menu_.name)
            return success_return(
                message="角色对应权限成功" if not fail_change_menu_name else f"权限修改部分成功，其中{fail_change_menu_name}已存在")
        else:
            return false_return(message="角色不存在")
