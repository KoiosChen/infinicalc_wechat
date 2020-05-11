from flask_restplus import Resource, reqparse
from ..models import Roles, Elements, roles_elements
from .. import db, default_api, logger
from ..common import success_return, false_return, session_commit
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
from ..public_method import get_table_data, get_table_data_by_id

roles_ns = default_api.namespace('roles', path='/roles', description='包括角色、元素、权限相关操作')

role_add_parser = reqparse.RequestParser()
role_add_parser.add_argument('name', required=True, help='新的角色名称', location='json')
role_add_parser.add_argument('elements', required=True, type=list, help='该角色可用的权限ID，list。例如，[1,3,4,5]', location='json')

role_change_parser = reqparse.RequestParser()
role_change_parser.add_argument('name', required=True, help='新的角色名称')

role_bind_elements_parser = reqparse.RequestParser()
role_bind_elements_parser.add_argument('elements', required=True, type=list,
                                       help='该角色可用的权限ID，list。例如，[1,3,4,5]，从/roles/query_elements获取',
                                       location='json')

role_delete_parser = reqparse.RequestParser()
role_delete_parser.add_argument('role_id', required=True, help='要删除的角色ID(Roles.id)')

role_change_parser = reqparse.RequestParser()
role_change_parser.add_argument('name', required=True, help='修改角色名称(Roles.name)')

query_element_parser = reqparse.RequestParser()
query_element_parser.add_argument('role_id', help='要查询的角色ID(Roles.id)， 若此字段为空，则返回所有')

return_json = roles_ns.model('ReturnRegister', return_dict)

page_parser.add_argument('Authorization', required=True, location='headers')


@roles_ns.route('')
class RoleApi(Resource):
    @roles_ns.expect(page_parser)
    @roles_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.query_roles")
    def get(self, info):
        """
        获取所有角色列表
        """
        args = page_parser.parse_args()
        return success_return(
            get_table_data(Roles, args, ['elements']),
            "请求成功"
        )

    @roles_ns.expect(head_parser)
    @roles_ns.doc(body=role_add_parser)
    @roles_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.add_roles")
    def post(self, info):
        """
        添加角色
        """
        args = role_add_parser.parse_args(strict=True)
        elements_list = [Elements.query.get(m) for m in args['elements']]
        logger.debug(elements_list)
        if not Roles.query.filter_by(name=args['name']).first():
            new_role = Roles(name=args['name'])
            db.session.add(new_role)
            for element_ in elements_list:
                new_role.elements.append(element_)
            return success_return(data={"new_role_id": new_role.id},
                                  message="角色添加成功") \
                       if session_commit() else false_return(message="角色添加失败"), 400
        else:
            return false_return(message=f"{args['name']}已经存在"), 400


@roles_ns.route("/<int:role_id>")
@roles_ns.expect(head_parser)
@roles_ns.param('role_id', 'the role id')
class RoleID(Resource):
    @roles_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.query_role")
    def get(self, **kwargs):
        return success_return(
            get_table_data_by_id(Roles, kwargs['role_id'], ['elements'])
        )

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
                message="角色添加失败"), 400
        else:
            return false_return(message=f"{name_tobe}已经存在"), 400

    @roles_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.delete_role")
    def delete(self, **kwargs):
        pass


@roles_ns.route('/<int:role_id>/elements')
@roles_ns.expect(head_parser)
@roles_ns.param('role_id', 'the role id')
class RoleElements(Resource):
    @roles_ns.doc(body=role_bind_elements_parser)
    @roles_ns.marshal_with(return_json)
    @permission_required("app.users.roles_api.bind_element_by_role_id")
    def put(self, **kwargs):
        """
        修改制定角色（role_id）对应的权限列表
        """
        args = role_bind_elements_parser.parse_args()
        role_id = kwargs['role_id']
        role_ = Roles.query.get(role_id)
        fail_change_element_name = list()
        now_elements = args['elements']
        elements_in_db = Elements.query.outerjoin(roles_elements).outerjoin(Roles).filter(
            Roles.id.__eq__(role_id)).all()
        old_elements = [e.id for e in elements_in_db]
        elements_tobe_added = set(now_elements) - set(old_elements)
        elements_tobe_deleted = set(old_elements) - set(now_elements)
        if role_:
            for element_ in [Elements.query.get(m) for m in elements_tobe_added]:
                if element_ not in role_.elements:
                    role_.elements.append(element_)
                else:
                    fail_change_element_name.append(element_.name)

            for element_ in [Elements.query.get(m) for m in elements_tobe_deleted]:
                if element_ in role_.elements:
                    role_.elements.remove(element_)
                else:
                    fail_change_element_name.append(element_.name)
            return success_return(
                message="角色对应权限成功" if not fail_change_element_name else f"权限修改部分成功，其中{fail_change_element_name}已存在")
        else:
            return false_return(message="角色不存在"), 400
