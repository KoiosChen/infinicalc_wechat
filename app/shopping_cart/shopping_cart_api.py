from flask_restplus import Resource, reqparse
from ..models import SKU, ShopOrders, Promotions
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, nesteddict
from ..decorators import permission_required
from ..swagger import return_dict, head_parser
from app.type_validation import checkout_sku_type
from collections import defaultdict
import datetime

shopping_cart_ns = default_api.namespace('购物车', path='/shopping_cart', description='购物车API')

return_json = shopping_cart_ns.model('ReturnRegister', return_dict)

shopping_cart_parser = reqparse.RequestParser()
shopping_cart_parser.add_argument('sku', required=True, type=checkout_sku_type,
                                  help="[{'id': {'required': True, 'type': str}, "
                                       " 'quantity': {'required': True, 'type': int},"
                                       " 'combo': {'type': str}}]"
                                       "combo中存放的是此sku对应的套餐促销活动中的利益表的ID，combo允许有多重组合套餐，所以在页面上呈现为多选一，选中的为对应的Benefits表的ID",
                                  location='json')


@shopping_cart_ns.route('')
@shopping_cart_ns.expect(head_parser)
class ProceedCheckOut(Resource):
    @shopping_cart_ns.doc(body=shopping_cart_parser)
    @shopping_cart_ns.marshal_with(return_json)
    @permission_required("frontstage.app.shopping_cart.check_out")
    def post(self, **kwargs):
        """显示购物车"""
        args = shopping_cart_parser.parse_args().get("sku")
        all_p = defaultdict(list)
        customer = kwargs['info']['user']
        classifies_promotions = nesteddict()
        brand_promotions = nesteddict()
        spu_promotions = nesteddict()
        sku_promotions = nesteddict()
        global_promotions = {"global": {"skus": [], "promotions": Promotions.query.filter_by(scope=1).all()}}

        def _check_promotions(the_promotions, key, sku_, obj, arg):
            """
            根据sku， spu， brand， classify归类促销活动
            :param key:
            :param sku_:
            :param obj:
            :return:
            """
            for k in ('skus', 'promotions'):
                if not isinstance(the_promotions[obj][k], list):
                    the_promotions[obj][k] = list()

            the_promotions[obj]['skus'].append({"sku": sku_, "quantity": arg['quantity'], "combo": arg.get('combo')})
            the_promotions[obj]['promotions'].extend(getattr(obj, key + '_promotions'))

        for sku in args:
            sku_obj = SKU.query.get(sku['id'])

            _check_promotions(eval('sku_promotions'), 'sku', sku_obj, sku_obj, sku)
            _check_promotions(eval('spu_promotions'), 'spu', sku_obj, sku_obj.the_spu, sku)
            _check_promotions(eval('brand_promotions'), 'brand', sku_obj, sku_obj.the_spu.brand, sku)
            _check_promotions(eval('classifies_promotions'), 'classifies', sku_obj, sku_obj.the_spu.classifies, sku)
            global_promotions['global']['skus'].append({"sku": sku_obj, "quantity": sku['quantity'], "combo": sku.get('combo')})

        for s in ('sku', 'spu', 'brand', 'classifies', 'global'):
            for key, sp in eval(s + '_promotions').items():
                if sp.get('promotions'):
                    total_fee = sum([sku['sku'].price for sku in sp['skus']])
                    total_quantity = sum([sku['quantity'] for sku in sp['skus']])
                    special = sum([sku['sku'].special for sku in sp['skus']])
                    """排除掉冲突的促销活动"""
                    p_groups = defaultdict(list)
                    # 把非group 0的组和对应的促销活动归类，然后把非0的促销活动POP出来
                    for p in sp['promotions']:
                        if p.groups.group_id != 0:
                            # 判断促销活动本身是否有效
                            if p.status == 1 and p.start_time <= datetime.datetime.now() <= p.end_time:
                                p_groups[p.groups].append(p)
                            sp['promotions'].pop(sp['promotions'].index(p))

                    # 把非0的组进行排序，因为所有非0组都是互斥的，按照优先级排序得到最优组
                    gs = [g for g in p_groups.keys()]
                    gs.sort(key=lambda x: x.priority)

                    # 把选举出来的非0组，追加到归类中，最终得到对应归类的有效的促销活动，下一步是判断范围内的sku的消费总额或者数量是否满足
                    if gs:
                        sp['promotions'].extend(p_groups[gs[0]])

                    # 判断用户属性及sku是否符合活动要求
                    for p in sp['promotions']:
                        # 用户属性是否符合
                        if not ShopOrders.query.filter_by(customer_id=customer.id).first():
                            sp['promotions'].pop(sp['promotions'].index(p))
                            continue
                        if not p.customer_level < customer.level:
                            sp['promotions'].pop(sp['promotions'].index(p))
                            continue
                        if p.gender != 0 and p.gender != customer.gender:
                            sp['promotions'].pop(sp['promotions'].index(p))
                            continue
                        if not datetime.timedelta(
                                days=p.age_min // 4 + p.age_min * 365) <= datetime.datetime.now().date() - customer.birthday <= datetime.timedelta(
                            days=p.age_max // 4 + p.age_max * 365):
                            sp['promotions'].pop(sp['promotions'].index(p))
                            continue

                        # 当前范围中是否有特价商品，当前活动是否允许使用在促销商品内，只要范围内有一个特价商品则失效当前促销活动
                        if p.with_special == 0 and special > 0:
                            sp['promotions'].pop(sp['promotions'].index(p))
                            continue

                        # 所购商品是否满足利益表
                        the_benefit = None
                        if p.accumulation == 0:
                            b = p.benefits[0]
                            if b.with_amount <= total_fee or b.with_quantity <= total_quantity:
                                the_benefit = b
                        elif p.accumulation == 1:
                            for b in p.benefits:
                                if b.with_amount <= total_fee or b.with_quantity <= total_quantity:
                                    the_benefit = b
                                    continue
                                else:
                                    break

                        if the_benefit is None:
                            sp['promotions'].pop(sp['promotions'].index(p))
                            continue

            print(eval(s + '_promotions'))
