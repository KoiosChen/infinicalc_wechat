from flask_restplus import Resource, fields, reqparse
from ..models import Classifies
from . import mall
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
from ..public_method import table_fields, new_data_obj
from ..decorators import permission_required
from ..swagger import head_parser
from .mall_api import mall_ns, return_json

add_classify_parser = reqparse.RequestParser()
add_classify_parser.add_argument('name', required=True, help='分类名称')

update_classify_parser = add_classify_parser.copy()
update_classify_parser.replace_argument('name', required=False, help='分类名称')


@mall_ns.route('/classifies')
@mall_ns.expect(head_parser)
class ClassifiesApi(Resource):
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.classifies.query_classifies")
    def get(self, **kwargs):
        """
        获取全部分类
        """
        fields_ = table_fields(Classifies)
        r = [{f: getattr(p, f) for f in fields_} for p in Classifies.query.all()]
        return success_return(r, "")

    @mall_ns.doc(body=add_classify_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.classifies.add_classify")
    def post(self, **kwargs):
        """新增分类"""
        args = add_classify_parser.parse_args()
        classify_db = Classifies.query.filter_by(name=args['name']).first()
        if classify_db:
            return false_return(message=f"<{args['name']}>已经存在")

        new_one = new_data_obj("Classifies", **{"name": args['name']})
        return success_return(message=f"分类<{args['name']}>添加成功，id：{new_one.id}")


@mall_ns.route('/classifies/<int:classify_id>')
@mall_ns.param('classify_id', '分类ID')
@mall_ns.expect(head_parser)
class ClassifyApi(Resource):
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.brands.query_classify")
    def get(self, **kwargs):
        """
        获取指定分类数据
        """
        fields_ = table_fields(Classifies)
        b = Classifies.query.get(kwargs['brand_id'])
        return success_return({f: getattr(b, f) for f in fields_}, "")

    @mall_ns.doc(body=update_classify_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.brands.update_classify")
    def put(self, **kwargs):
        """更新品牌"""
        args = update_classify_parser.parse_args()
        classify = Classifies.query.get(kwargs['classify_id'])
        for k, v in args.items():
            if hasattr(classify, k):
                setattr(classify, k, v)
            else:
                return false_return(message=f"{k}属性错误"), 400
        return success_return(message=f"分类更新成功{args.keys()}")

    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.brands.delete_brand")
    def delete(self, **kwargs):
        """删除分类"""
        classify = Classifies.query.get(kwargs['classify_id'])
        db.session.delete(classify)
        return success_return() if session_commit() else false_return(message="删除分类失败")
