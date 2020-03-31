from flask import jsonify, request
from flask_restplus import Resource, fields, reqparse
from ..models import Users, Roles, Menu, Permissions, role_menu
from . import menus
from app.auth import auths
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
import datetime
from ..decorators import permission_required
from ..swagger import return_dict, head_parser

menus_ns = default_api.namespace('menus', path='/menus', description='包括菜单相关操作')

return_json = menus_ns.model('ReturnRegister', return_dict)


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
    def get(self):
        """
        查询所有Menus列表
        :return:
        """
        return success_return(get_menus(), "请求成功")

    def post(self):
        """
        创建权限
        :return:
        """


@menus_ns.route('/<int:menu_id>')
@menus_ns.expect(head_parser)
class QueryMenu(Resource):
    @menus_ns.marshal_with(return_json)
    @permission_required("app.menus.menus_api.get_menu_by_id")
    def get(self):
        """
        查询指定的menu
        :return:
        """
        return success_return(get_menus(role_id), "请求成功")

    def put(self):
        """
        修改menu
        :return:
        """
        pass

    def delete(self):
        """
        删除menu
        :return:
        """
        pass
