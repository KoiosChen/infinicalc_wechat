from flask_restplus import Resource, fields, reqparse
from ..models import Layout, SKULayout, SKU
from . import layout
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import table_fields, new_data_obj, get_table_data
from ..decorators import permission_required
from ..swagger import head_parser, return_dict, page_parser

layout_ns = default_api.namespace('layout', path='/layout', description='页面板块')

return_json = layout_ns.model('ReturnRegister', return_dict)

add_layout_parser = reqparse.RequestParser()
add_layout_parser.add_argument('name', required=True, help='页面板块名称')
add_layout_parser.add_argument('desc', help='描述、备注')

add_sku_layout_parser = reqparse.RequestParser()
add_sku_layout_parser.add_argument('sku', type=list, required=True, location='json',
                                   help='需要添加到sku list，例如[{"id": sku_id, "order": 1}]')

delete_sku_in_layout_parser = reqparse.RequestParser()
delete_sku_in_layout_parser.add_argument('sku', required=True, type=list, location='json',
                                         help='需要删除的sku 列表, 例如[ a, b, c]')

update_sku_layout_parser = add_sku_layout_parser.copy()
update_sku_layout_parser.replace_argument('sku', required=True, type=list, location='json',
                                          help='需要变更到sku list，例如[{"id": sku_id, "order": 1, "status": 1}]')


def query_sku_layout(layout_id=None):
    fields_ = table_fields(SKULayout)
    if layout_id is None:
        all_layout = SKULayout.query.all()
    else:
        all_layout = SKULayout.query.filter_by(layout_id=layout_id).all()
    r = list()
    for lay in all_layout:
        tmp = dict()
        for f in fields_:
            if f == 'layout_id':
                tmp['layout'] = {'id': lay.layout_id, 'name': lay.layout.name}
            elif f == 'sku_id':
                tmp['sku'] = {'id': lay.sku_id, 'name': lay.layout_sku.name}
            elif f == 'create_at':
                tmp['create_at'] = str(lay.create_at)
            else:
                tmp[f] = getattr(lay, f)
        r.append(tmp)
    return r


@layout_ns.route('')
@layout_ns.expect(head_parser)
class LayoutApi(Resource):
    @layout_ns.marshal_with(return_json)
    @layout_ns.doc(body=page_parser)
    @permission_required("app.mall.layout.query_layouts")
    def get(self, **kwargs):
        """
        获取全部页面板块设置
        """
        args = page_parser.parse_args()
        return success_return(get_table_data(Layout, args, removes=['create_at']), "")

    @layout_ns.doc(body=add_layout_parser)
    @layout_ns.marshal_with(return_json)
    @permission_required("app.mall.layout.add_layout")
    def post(self, **kwargs):
        """新增页面板块，仅用于定义板块名称"""
        args = add_layout_parser.parse_args()
        new_one = new_data_obj("Layout", **{"name": args['name']})
        if new_one and new_one['status']:
            new_one['obj'].desc = args.get('desc')
            return submit_return(f"页面板块{args['name']}添加成功，id：{new_one['obj'].id}", f"页面板块{args['name']}添加描述失败")
        else:
            return false_return(message=f"页面板块{args['name']}已经存在"), 400


@layout_ns.route('/sku')
@layout_ns.expect(head_parser)
class AllSKULayoutApi(Resource):
    @layout_ns.marshal_with(return_json)
    @permission_required("app.mall.layout.all_sku_in_layout")
    def get(self, **kwargs):
        """
        获取所有页面板块对应的SKU及其排序
        """
        return success_return(query_sku_layout(), "")


@layout_ns.route('/<int:layout_id>/sku')
@layout_ns.param('layout_id', '页面ID')
@layout_ns.expect(head_parser)
class SKULayoutApi(Resource):
    @layout_ns.marshal_with(return_json)
    @permission_required("app.mall.layout.query_sku_in_layout")
    def get(self, **kwargs):
        """
        获取指定页面板块对应的SKU及其排序
        """
        layout_id = kwargs.get('layout_id')
        return success_return(query_sku_layout(layout_id), "")

    @layout_ns.doc(body=add_sku_layout_parser)
    @layout_ns.marshal_with(return_json)
    @permission_required("app.mall.layout.add_sku_to_layout")
    def post(self, **kwargs):
        """
        新增sku到页面布局中
        """
        args = update_sku_layout_parser.parse_args()
        sku_list = args.get('sku')
        failed = []
        for sl in sku_list:
            new_one = new_data_obj("SKULayout", **{'layout_id': kwargs['layout_id'], 'sku_id': sl['id']})
            if not new_one.get('status'):
                failed.append({'layout_id': kwargs['layout_id'], 'sku_id': sl['id']})

        return submit_return("添加sku到页面板块中成功", "部分SKU已存在该页面板块")


@layout_ns.doc(body=update_sku_layout_parser)
@layout_ns.marshal_with(return_json)
@permission_required("app.mall.layout.update_sku_in_layout")
def put(self, **kwargs):
    """
    修改页面布局中的sku(如果传递的SKU不存在，会新增）
    """
    args = update_sku_layout_parser.parse_args()
    sku_list = args.get('sku')
    for sl in sku_list:
        if SKU.query.get(sl['id']):
            update_one = new_data_obj("SKULayout", **{'layout_id': kwargs['layout_id'],
                                                      'sku_id': sl['id']})
            if sl.get('order'):
                update_one.order = sl['order']
            if eval(sl.get('status')) in (0, 1):
                update_one.status = sl['status']
        else:
            return false_return(f'<{sl["id"]}> 此SKU 不存在 '), 400
    return success_return(message="更新sku到页面板块中成功") if session_commit() else false_return(message='更新页面板块失败'), 400


@layout_ns.doc(body=delete_sku_in_layout_parser)
@layout_ns.marshal_with(return_json)
@permission_required("app.mall.layout.delete_sku_in_layout")
def delete(self, **kwargs):
    """删除页面板块中的SKU"""
    args = delete_sku_in_layout_parser.parse_args()
    for sku in args['sku']:
        to_delete = SKULayoutApi.query.filter_by(layout_id=kwargs['layout_id'], sku_id=sku).first()
        if to_delete:
            db.session.delete(to_delete)
    return success_return(message="删除页面板块中的SKU失败") if session_commit() else false_return(message="删除页面板块中的SKU失败"), 400
