from flask import jsonify, request
from flask_restplus import Resource, fields, reqparse
from ..models import Users, Roles, Menu, Permissions, role_menu
from . import permissions
from app.auth import auths
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
import datetime
from ..decorators import permission_required
from ..swagger import return_dict, head_parser

permission_ns = default_api.namespace('permissions', path='/permissions', description='包括权限相关操作')

return_json = permission_ns.model('ReturnRegister', return_dict)


@permission_ns.route('')
@permission_ns.expect(head_parser)
class QueryPermissions(Resource):
    def get(self):
        """
        获取全部权限
        :return:
        """
        pass

    def post(self):
        """创建权限"""
        pass


@permission_ns.route('/<int:permission_id>')
@permission_ns.expect(head_parser)
class PermissionById(Resource):
    def get(self):
        """
        获取特定权限
        :return:
        """
        pass

    def delete(self):
        """删除权限"""
        pass

    def put(self):
        """修改权限"""
        pass