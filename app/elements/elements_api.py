from flask_restplus import Resource, reqparse, cors
from flask import request
from ..models import Elements
from . import elements
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id
from ..decorators import permission_required, allow_cross_domain
from ..swagger import return_dict, head_parser, page_parser

elements_ns = default_api.namespace('elements', path='/elements', description='包括元素相关操作')

return_json = elements_ns.model('ReturnRegister', return_dict)

add_element_parser = reqparse.RequestParser()
add_element_parser.add_argument('name', required=True, help='新的元素名称')
add_element_parser.add_argument('icon', help='元素图标对应图片的存储路径')
add_element_parser.add_argument('url', help='元素的url')
add_element_parser.add_argument('order', help='同等级元素的排列顺序')
add_element_parser.add_argument('bg_color', help='对应类型的背景色')
add_element_parser.add_argument('type', required=True, help='元素类型，包括menu, button, api等')
add_element_parser.add_argument('parent_id', help='当类型为元素时，存在父节点，即目录')
add_element_parser.add_argument('permission', required=True, help='例如：app.elements.elements_api.get_element')

update_element_parser = add_element_parser.copy()
update_element_parser.replace_argument('name', required=False, help='新的元素名称')
update_element_parser.add_argument('type', required=False, help='元素类型，包括menu, button, api等')
update_element_parser.add_argument('permission', required=False, help='例如：app.elements.elements_api.get_element')

page_parser.add_argument('permission', help='搜索permission字段', location='args')
page_parser.add_argument('name', help='搜索name字段', location='args')
page_parser.add_argument('Authorization', required=True, location='headers')


@elements_ns.route('')
@elements_ns.expect(head_parser)
class QueryElements(Resource):
    @elements_ns.marshal_with(return_json)
    @elements_ns.doc(body=page_parser)
    @permission_required("app.elements.elements_api.get_elements")
    def get(self, **kwargs):
        """
        查询所有Elements列表
        """
        args = page_parser.parse_args()
        args['search'] = dict()
        if args.get("permission"):
            args['search']['permission'] = args.get('permission')
        if args.get("name"):
            args['search']['name'] = args.get('name')
        return success_return(get_table_data(Elements, args, ['children']), "请求成功")

    @elements_ns.doc(body=add_element_parser)
    @elements_ns.marshal_with(return_json)
    @permission_required("app.elements.elements_api.add_element")
    def post(self, **kwargs):
        """
        创建页面元素
        """
        args = add_element_parser.parse_args()
        new_element = new_data_obj("Elements", **{"name": args['name']})
        for key, value in args.items():
            if key != 'name':
                if key == 'parent_id' and new_element['obj'].id == value:
                    return false_return(message="父节点不能为自身"), 400
                if value:
                    setattr(new_element['obj'], key, value)
        db.session.add(new_element['obj'])
        commit_status = session_commit()
        if commit_status['code'] == 'success':
            return success_return(data={'id': new_element['obj'].id}, message="元素创建成功")
        else:
            false_return(message=f"元素创建失败, {commit_status['message']}"), 400


@elements_ns.route('/<int:element_id>')
@elements_ns.expect(head_parser)
class QueryElement(Resource):
    @elements_ns.marshal_with(return_json)
    @permission_required("app.elements.elements_api.get_element")
    def get(self, **kwargs):
        """
        通过element id查询element
        """
        result = get_table_data_by_id(Elements, kwargs['element_id'], appends=['children'])
        return false_return(message=f"无对应资源") if not result else success_return(result, "请求成功")

    @elements_ns.doc(body=update_element_parser)
    @elements_ns.marshal_with(return_json)
    @permission_required("app.elements.elements_api.update_element")
    def put(self, **kwargs):
        """
        修改element
        """
        args = update_element_parser.parse_args()
        the_element = Elements.query.get(kwargs['element_id'])
        if not the_element:
            return false_return(message=f"<{kwargs['element_id']}>不存在")

        try:
            for key, value in args.items():
                if key == 'name' and Elements.query.filter(Elements.name.__eq__(value), Elements.id.__ne__(kwargs['element_id'])).first():
                    return false_return(message="元素名已存在")
                elif value:
                    setattr(the_element, key, value)
            db.session.add(the_element)
            if session_commit():
                return success_return(message="元素修改成功")
            else:
                return false_return(message=f"元素修改数据提交失败"), 400
        except Exception as e:
            db.session.rollback()
            return false_return(message=f"更新元素失败：{e}"), 400

    @elements_ns.marshal_with(return_json)
    @permission_required("app.elements.elements_api.delete_element")
    def delete(self, **kwargs):
        """
        删除element
        """
        tobe_delete = Elements.query.get(kwargs['element_id'])
        if tobe_delete:
            roles = tobe_delete.elements_roles.all()
            if not roles:
                db.session.delete(tobe_delete)
                if session_commit().get("code") == 'success':
                    return success_return(message="元素删除成功")
                else:
                    return false_return(message="元素删除失败"), 400
            else:
                return false_return(message=f"此元素被占用，不可删除：{roles}"), 400
        else:
            return false_return(message=f"元素不存在"), 400
