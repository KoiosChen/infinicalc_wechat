from flask_restplus import Resource, fields, reqparse
from ..models import Layout, SKULayout, SKU, Permission
from . import layout
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import table_fields, new_data_obj, get_table_data, get_table_data_by_id
from ..decorators import permission_required
from ..swagger import head_parser, return_dict, page_parser
from collections import defaultdict

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


def query_sku_layout(layout_name=None):
    if layout_name is None:
        all_layout = SKULayout.query.filter_by(status=1).all()
    else:
        layout = Layout.query.filter_by(name=layout_name).first()
        all_layout = SKULayout.query.filter_by(layout_id=layout.id, status=1).all()
    r = defaultdict(dict)
    sku_fields = table_fields(SKU)
    for lay in all_layout:
        if "sku" not in r[lay.layout.name].keys():
            r[lay.layout.name]["sku"] = list()

        sku_data = get_table_data_by_id(SKU, lay.sku_id, ['id', 'name', 'real_price', 'objects', 'status','values'],
                                        sku_fields,
                                        search={"status": 1})
        sku_data['order'] = lay.order
        r[lay.layout.name]["sku"].append(sku_data)
    for layout_name in r.keys():
        r[layout_name]['sku'].sort(key=lambda x:x["order"])
    return r


@layout_ns.route('')
@layout_ns.expect(head_parser)
class LayoutApi(Resource):
    @layout_ns.marshal_with(return_json)
    @layout_ns.doc(body=page_parser)
    @permission_required([Permission.USER, "app.mall.layout.query_layouts"])
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
    @permission_required([Permission.USER, "app.mall.layout.all_sku_in_layout"])
    def get(self, **kwargs):
        """
        获取所有页面板块对应的SKU及其排序
        """
        return success_return(query_sku_layout(), "")


@layout_ns.route('/<string:layout_name>/sku')
@layout_ns.param('layout_name', '页面ID')
@layout_ns.expect(head_parser)
class SKULayoutApi(Resource):
    @layout_ns.marshal_with(return_json)
    @permission_required([Permission.USER, "app.mall.layout.query_sku_in_layout"])
    def get(self, **kwargs):
        """
        获取指定页面板块对应的SKU及其排序
        """
        layout_name = kwargs.get('layout_name')
        return success_return(query_sku_layout(layout_name), "")

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
        layout = Layout.query.filter_by(name=kwargs['layout_name']).first()
        for sl in sku_list:
            new_one = new_data_obj("SKULayout", **{'layout_id': layout.id, 'sku_id': sl['id'], 'order': sl['order']})
            if not new_one.get('status'):
                failed.append({'layout_id': layout.id, 'sku_id': sl['id']})

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
    return submit_return("更新sku到页面板块中成功", '更新页面板块失败')


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
    return submit_return("删除页面板块中的SKU失败", "删除页面板块中的SKU失败")
