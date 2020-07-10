from flask_restplus import Resource, reqparse
from ..models import PromotionGroups, Promotions, Coupons, CouponReady, Benefits
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, submit_return
from ..public_method import new_data_obj, table_fields, get_table_data, get_table_data_by_id
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser

promotion_groups_ns = default_api.namespace('promotion_groups', path='/promotion_groups', description='包括促销活动组设置相关操作')

return_json = promotion_groups_ns.model('ReturnRegister', return_dict)

add_promotion_group_parser = reqparse.RequestParser()
add_promotion_group_parser.add_argument('name', required=True, help='促销活动组名称，唯一性约束')
add_promotion_group_parser.add_argument('desc', help='促销活动描述')
add_promotion_group_parser.add_argument('group_id', required=True,
                                        help='组ID， 0 为特殊组，特殊组和任何组不互斥。group_id 为-1表示是发优惠券，>=0的group，为活动')
add_promotion_group_parser.add_argument('priority', required=True, help='1-10, 10优先级最低，当有组互斥时，使用优先级最高的，0优先级最高')

update_promotion_group_parser = add_promotion_group_parser.copy()
update_promotion_group_parser.replace_argument('name', required=False, help='新的元素名称')
update_promotion_group_parser.add_argument('group_id', required=False, help='组ID， 0 为特殊组，特殊组和任何组不互斥')
update_promotion_group_parser.add_argument('priority', required=False, help='1-10, 10优先级最低，当有组互斥时，使用优先级最高的，0优先级最高')


@promotion_groups_ns.route('')
@promotion_groups_ns.expect(head_parser)
class QueryPromotionGroups(Resource):
    @promotion_groups_ns.marshal_with(return_json)
    @promotion_groups_ns.doc(body=page_parser)
    @permission_required("app.promotion_groups.promotion_groups_api.query_promotion_groups_all")
    def get(self, **kwargs):
        """
        查询所有PromotionGroups列表
        """
        args = page_parser.parse_args()
        return success_return(get_table_data(PromotionGroups, args), "请求成功")

    @promotion_groups_ns.doc(body=add_promotion_group_parser)
    @promotion_groups_ns.marshal_with(return_json)
    @permission_required("app.promotion_groups.promotion_groups_api.add_promotion_group")
    def post(self, **kwargs):
        """
        创建促销活动组
        """
        args = add_promotion_group_parser.parse_args()
        new_group = new_data_obj("PromotionGroups",
                                 **{"name": args['name'],
                                    "group_id": args['group_id'],
                                    "priority": args['priority']
                                    }
                                 )
        if args.get('desc') and new_group.get('status'):
            setattr(new_group['obj'], 'desc', args.get('desc'))
        else:
            return false_return(message=f'{args} 已存在')
        db.session.add(new_group['obj'])
        if session_commit().get("code") == "success":
            return success_return(data={'id': new_group['obj'].id}, message="促销活动组创建成功")
        else:
            return false_return(message="促销活动组创建失败")


@promotion_groups_ns.route('/<int:promotion_group_id>')
@promotion_groups_ns.expect(head_parser)
class QueryPromotionGroup(Resource):
    @promotion_groups_ns.marshal_with(return_json)
    @permission_required("app.promotion_groups.promotion_groups_api.get_promotion_group")
    def get(self, **kwargs):
        """
        通过promotion_group_id查询促销活动组
        """
        result = get_table_data_by_id(PromotionGroups, kwargs['promotion_id'])
        return false_return(message=f"无对应资源") if not result else success_return(result, "请求成功")

    @promotion_groups_ns.doc(body=update_promotion_group_parser)
    @promotion_groups_ns.marshal_with(return_json)
    @permission_required("app.promotion_groups.promotion_groups_api.update_promotion_group")
    def put(self, **kwargs):
        """
        修改促销活动组
        """
        args = update_promotion_group_parser.parse_args()
        the_group = PromotionGroups.query.get(kwargs['promotion_group_id'])
        if not the_group:
            return false_return(message=f"<{kwargs['promotion_group_id']}>不存在")

        try:
            for key, value in args.items():
                if key == 'name' and PromotionGroups.query.filter_by(name=value).first():
                    return false_return(message="促销活动组名已存在")
                elif key == 'group_id' and PromotionGroups.query.filter_by(name=value).first():
                    return false_return(message="促销活动组ID已存在")
                elif value:
                    setattr(the_group, key, value)
            db.session.add(the_group)
            return submit_return("促销活动组修改成功", "促销活动组修改数据提交失败")

        except Exception as e:
            db.session.rollback()
            return false_return(message=f"更新促销活动组失败：{e}"), 400

    @promotion_groups_ns.marshal_with(return_json)
    @permission_required("app.app.promotion_groups.promotion_groups_api.delete_promotion_group")
    def delete(self, **kwargs):
        """
        删除促销活动组
        """
        tobe_delete = PromotionGroups.query.get(kwargs['promotion_group_id'])
        if tobe_delete:
            promotions = tobe_delete.promotions.all()
            if not promotions:
                db.session.delete(tobe_delete)
                return submit_return("促销活动组删除成功", "促销活动组删除失败")
            else:
                return false_return(message=f"此促销活动组被占用，不可删除：{promotions}"), 400
        else:
            return false_return(message=f"促销活动组不存在"), 400
