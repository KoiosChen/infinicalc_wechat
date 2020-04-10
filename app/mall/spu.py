from flask_restplus import Resource, fields, reqparse
from ..models import SPU, Standards, spu_standards
from . import mall
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit
from ..public_method import table_fields, new_data_obj
from ..decorators import permission_required
from ..swagger import head_parser
from .mall_api import mall_ns, return_json

add_spu_parser = reqparse.RequestParser()
add_spu_parser.add_argument('name', required=True, help='SPU的名称，例如iPhone6')
add_spu_parser.add_argument('sub_name', help='SPU子标题，可为空')
add_spu_parser.add_argument('brand_id', required=True, help='品牌，如：苹果。从/brands接口获取')
add_spu_parser.add_argument('classify_id', required=True, help='分类，如：手机。 从/classifies接口获取')
# add_spu_parser.add_argument('standards', type=list, location='json',
#                             help='此SPU相关的产品规格，用list传递，包含规格的ID， 用/standards接口获取')

update_spu_parser = add_spu_parser.copy()
update_spu_parser.replace_argument('name', required=False)
update_spu_parser.replace_argument('brand_id', required=False)
update_spu_parser.replace_argument('classify_id', required=False)

spu_standard_parser = reqparse.RequestParser()
spu_standard_parser.add_argument('standards', type=list, help='传递最新的完整的规格列表，整体更新数据库', location='json')


@mall_ns.route('/spu')
@mall_ns.expect(head_parser)
class SPUApi(Resource):
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.spu.query_spu_all")
    def get(self, **kwargs):
        """
        获取全部SPU
        """
        fields_ = table_fields(SPU)
        fields_.append("sku")
        result = list()
        for p in SPU.query.all():
            tmp = dict()
            for f in fields_:
                if f == 'sku':
                    tmp[f] = {s.id: s.name for s in p.sku.all()}
                else:
                    tmp[f] = getattr(p, f)
            result.append(tmp)

        return success_return(result, "")

    @mall_ns.doc(body=add_spu_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.sku.add_spu")
    def post(self, **kwargs):
        """新增SPU"""
        args = add_spu_parser.parse_args()
        spu_db = SPU.query.filter_by(brand_id=args['brand_id'], name=args['name']).first()
        if spu_db:
            return false_return(message=f"<{args['name']}>已经存在其对应的品牌中")

        new_one = new_data_obj("SPU", **{"name": args['name'],
                                         "sub_name": args.get('sub_name'),
                                         "brand_id": args['brand_id'],
                                         "classify_id": args['classify_id']})

        return success_return(message=f"SPU {args['name']} 添加到Brand ID: {args['brand_id']}成功，id：{new_one['obj'].id}")


@mall_ns.route('/spu/<string:spu_id>')
@mall_ns.expect(head_parser)
class PerSPUApi(Resource):
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.spu.query_per_spu")
    def get(self, **kwargs):
        """
        获取指定ID的SPU
        """
        fields_ = table_fields(SPU)
        fields_.extend(["sku", "standards"])
        p = SPU.query.get(kwargs['spu_id'])
        tmp = dict()
        for f in fields_:
            if f == 'sku':
                tmp[f] = [{'id': s.id, 'name': s.name} for s in p.sku]
            elif f == 'standards':
                tmp[f] = [{'id': s.id, 'name': s.name} for s in p.standards]
            else:
                tmp[f] = getattr(p, f)

        return success_return(tmp, "")

    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.sku.delete_spu")
    def delete(self, **kwargs):
        """删除SPU"""
        spu_db = SPU.query.get(kwargs['spu_id'])
        if spu_db:
            db.session.delete(spu_db)
            return success_return(message=f"SPU {kwargs['spu_id']}已被删除") if session_commit() else false_return(
                message=f"SPU {kwargs['spu_id']}删除失败")
        else:
            return false_return(f"不存在{kwargs['spu_id']}")

    @mall_ns.doc(body=update_spu_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.sku.update_spu")
    def put(self, **kwargs):
        """更新指定ID的SPU"""
        args = update_spu_parser.parse_args()
        spu_db = SPU.query.get(kwargs['spu_id'])
        for k, v in args.items():
            if hasattr(spu_db, k) and v:
                setattr(spu_db, k, v)
            else:
                return false_return(message=f"{k}属性错误"), 400
        return success_return(message=f"SPU更新成功{args.keys()}")


@mall_ns.route('/spu/<string:spu_id>/standards')
@mall_ns.expect(head_parser)
class PerSPUStandard(Resource):
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.spu.query_per_spu_standard")
    def get(self, **kwargs):
        """
        获取指定ID的SPU对应的产品规格列表
        """
        standards = Standards.query.outerjoin(spu_standards).outerjoin(SPU).filter(
            SPU.id.__eq__(kwargs.get("spu_id"))).all()
        return success_return(data=[{"id": s.id, "name": s.name} for s in standards])

    @mall_ns.doc(body=spu_standard_parser)
    @mall_ns.marshal_with(return_json)
    @permission_required("app.mall.sku.update_spu_standards")
    def put(self, **kwargs):
        """修改spu对应规格，需传递所有规格ID"""

        args = spu_standard_parser.parse_args()
        spu_id = kwargs['spu_id']
        spu_ = SPU.query.get(spu_id)
        fail_change_spu_name = list()
        now_standards = args['standards']
        standards_in_db = Standards.query.outerjoin(spu_standards).outerjoin(SPU).filter(SPU.id.__eq__(spu_id)).all()
        old_standards = [s.id for s in standards_in_db]
        standards_tobe_added = set(now_standards) - set(old_standards)
        standards_tobe_deleted = set(old_standards) - set(now_standards)
        if spu_:
            for standard_ in [Standards.query.get(s) for s in standards_tobe_added]:
                if standard_ not in spu_.standards:
                    spu_.standards.append(standard_)
                else:
                    fail_change_spu_name.append(standard_.name)

            for standard_ in [Standards.query.get(s) for s in standards_tobe_deleted]:
                if standard_ in spu_.standards:
                    spu_.standards.remove(standard_)
                else:
                    fail_change_spu_name.append(standard_.name)
            return success_return(
                message="SPU对应规格修改成功" if not fail_change_spu_name else f"规格修改部分成功，其中{fail_change_spu_name}已存在")
        else:
            return false_return(message="SPU不存在")
