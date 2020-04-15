from flask_restplus import Resource, reqparse
from ..models import Permissions
from . import permissions
from .. import db, default_api
from ..common import success_return, false_return, session_commit
from ..public_method import table_fields, new_data_obj, get_table_data
from ..decorators import permission_required
from ..swagger import return_dict, head_parser
from sqlalchemy import or_

permission_ns = default_api.namespace('permissions', path='/permissions', description='包括权限相关操作')

return_json = permission_ns.model('ReturnRegister', return_dict)

add_permission_parser = reqparse.RequestParser()
add_permission_parser.add_argument('name', required=True, help='权限名称')
add_permission_parser.add_argument('action', required=True, help='权限标识')

update_permission_parser = reqparse.RequestParser()
update_permission_parser.add_argument('name', help='权限名称')
update_permission_parser.add_argument('action', help='权限标识')


@permission_ns.route('')
@permission_ns.expect(head_parser)
class QueryPermissions(Resource):
    @permission_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.query_permissions")
    def get(self, **kwargs):
        """
        获取全部权限
        """
        return success_return(get_table_data(Permissions))

    @permission_ns.doc(body=add_permission_parser)
    @permission_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.add_permission")
    def post(self, **kwargs):
        """创建权限"""
        args = add_permission_parser.parse_args()
        new_one = new_data_obj("Permissions", **{"name": args['name'], "action": args['action']})
        if not new_one:
            return false_return(message=f"创建权限失败"), 400
        if not new_one['status']:
            return false_return(message=f"<{args['action']}>已经存在，当前权限名为<{new_one['obj'].name}>"), 400

        return success_return(data={'id': new_one['obj'].id},
                              message=f"{args['name']}: {args['action']} 添加成功，id：{new_one['obj'].id}")


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

    @permission_ns.doc(body=update_permission_parser)
    @permission_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.delete_permission_by_id")
    def put(self, **kwargs):
        """修改权限"""
        args = update_permission_parser.parse_args()
        if Permissions.query.filter(
                or_(Permissions.name.__eq__(args['name']), Permissions.action.__eq__(args['action']))).all():
            return false_return('权限修改失败，内容冲突'), 400

        p = Permissions.query.get(kwargs['permission_id'])
        if not p:
            return false_return(f"ID {kwargs['permission_id']}不存在"), 400

        try:
            fields_ = table_fields(Permissions, removes=['id'])
            for f in fields_:
                if args.get(f):
                    setattr(p, f, args.get(f))
            return success_return(message=f'<{p.id}>更新成功')
        except Exception as e:
            return false_return(message=f'更新<{kwargs["permission_id"]}>失败，{e}'), 400

    @permission_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.delete_permission_by_id")
    def delete(self, **kwargs):
        """删除权限"""
        p = Permissions.query.get(kwargs['permission_id'])
        if not p:
            return false_return(message=f'此权限不存在'), 400

        elements = p.permissions_elements.all()
        if not elements:
            db.session.delete(p)
            return success_return(message="权限删除成功") if session_commit() else false_return(message='权限删除时数据提交失败'), 400
        else:
            return false_return(message=f"权限被占用，不可删除：{elements}"), 400
