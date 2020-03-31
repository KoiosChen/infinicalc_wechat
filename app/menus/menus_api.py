from flask import jsonify, request
from flask_restplus import Resource, fields, reqparse
from ..models import Users, Roles, Menu, Permissions, role_menu
from . import menus
from app.auth import auths
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
from ..public_method import new_data_obj
import datetime
from ..decorators import permission_required
from ..swagger import return_dict, head_parser

menus_ns = default_api.namespace('menus', path='/menus', description='包括菜单相关操作')

return_json = menus_ns.model('ReturnRegister', return_dict)

menu_add_parser = reqparse.RequestParser()
menu_add_parser.add_argument('name', required=True, help='新的菜单名称', location='json')
menu_add_parser.add_argument('icon', help='菜单图标对应图片的存储路径', location='json')
menu_add_parser.add_argument('url', help='菜单的url', location='json')
menu_add_parser.add_argument('order', help='同等级菜单的排列顺序', location='json')
menu_add_parser.add_argument('bg_color', help='对应类型的背景色', location='json')
menu_add_parser.add_argument('type', help='菜单类型，包括目录，菜单, 按钮', location='json')
menu_add_parser.add_argument('parent_id', help='当类型为菜单时，存在父节点，即目录', location='json')
menu_add_parser.add_argument('permission', required=True, help='权限ID，list。例如，[1,3,4,5], 从/permissions接口获取',
                             location='json')


def get_menus(menu_id=None):
    menu_fields = Menu.__table__.columns.keys()
    menu_fields.append("permissions")
    menus = Menu.query.all() if menu_id is None else Menu.query.filter_by(id=menu_id).all()
    return_menu = list()

    for menu in menus:
        tmp = dict()
        for f in menu_fields:
            if f == 'permissions':
                tmp[f] = menu.permissions.action
            else:
                tmp[f] = getattr(menu, f)
        return_menu.append(tmp)

    return return_menu


@menus_ns.route('')
@menus_ns.expect(head_parser)
class QueryMenus(Resource):
    @menus_ns.marshal_with(return_json)
    @permission_required("app.menus.menus_api.get_menus")
    def get(self, **kwargs):
        """
        查询所有Menus列表
        :return:
        """
        return success_return(get_menus(), "请求成功")

    @menus_ns.doc(body=menu_add_parser)
    @menus_ns.marshal_with(return_json)
    @permission_required("app.menus.menus_api.add_menu")
    def post(self, **kwargs):
        """
        创建权限
        :return:
        """
        args = menu_add_parser.parse_args()
        new_menu = new_data_obj("Menu", **{"name": args['name']})
        for key, value in args.items():
            if key != 'name':
                setattr(new_menu, key, value)
        db.session.add(new_menu)
        return success_return(message="菜单创建成功") if session_commit() else false_return(message="菜单创建失败")


@menus_ns.route('/<int:menu_id>')
@menus_ns.expect(head_parser)
class QueryMenu(Resource):
    @menus_ns.marshal_with(return_json)
    @permission_required("app.menus.menus_api.get_menu")
    def get(self, **kwargs):
        """
        通过menu id查询menu
        """
        return success_return(get_menus(kwargs['menu_id']), "请求成功")

    @menus_ns.doc(body=menu_add_parser)
    @menus_ns.marshal_with(return_json)
    @permission_required("app.menus.menus_api.change_menu")
    def put(self, **kwargs):
        """
        修改menu
        """
        args = menu_add_parser.parse_args()
        the_menu = Menu.query.get(kwargs['menu_id'])
        for key, value in args.items():
            if key == 'name' and Menu.query.filter_by(name=value).first():
                return false_return(message="菜单名已存在")
            else:
                setattr(the_menu, key, value)
        db.session.add(the_menu)
        return success_return(message="菜单修改成功") if session_commit() else false_return(message="菜单修改失败")

    @menus_ns.marshal_with(return_json)
    @permission_required("app.menus.menus_api.delete_menu")
    def delete(self, **kwargs):
        """
        删除menu
        """
        tobe_delete = Menu.query.get(kwargs['menu_id'])
        db.session.delete(tobe_delete)
        return success_return(message="菜单删除成功") if session_commit() else false_return(message="菜单删除失败")
