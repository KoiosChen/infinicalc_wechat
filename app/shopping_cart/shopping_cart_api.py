from flask_restplus import Resource, reqparse
from ..models import SKU, ShopOrders, Promotions
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, nesteddict
from ..decorators import permission_required
from ..swagger import return_dict, head_parser
from app.type_validation import checkout_sku_type
from collections import defaultdict
import datetime
from decimal import Decimal

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
        member_card = None
        member_cards = customer.member_card
        for card in member_cards:
            if card and card.status == 1:
                member_card = card
        classifies_promotions = nesteddict()
        brand_promotions = nesteddict()
        spu_promotions = nesteddict()
        sku_promotions = nesteddict()
        global_promotions = {"global": {"skus": [], "promotions": Promotions.query.filter_by(scope=1, status=1).all()}}

        def _check_promotions(the_promotions, key_, sku_, obj_, arg):
            """
            根据sku， spu， brand， classify归类促销活动
            :param key_:
            :param sku_:
            :param obj_:
            :return:
            """
            for k in ('skus', 'promotions'):
                if not isinstance(the_promotions[obj_][k], list):
                    the_promotions[obj_][k] = list()
            price = sku_.price * sku_.discount if member_card is None else sku_.member_price * member_card.discount
            tmp = {"sku": sku_, "quantity": arg['quantity'], "price": price, "combo": arg.get('combo')}
            # 判断促销活动是否是秒杀
            if sku_.seckill_price:
                tmp['seckill_price'] = sku_.seckill_price

            if obj_ != 'global':
                promotions = getattr(obj_, key_ + '_promotions')
            else:
                promotions = the_promotions[obj_]['promotions']
            for pro in promotions:

                # 检查促销活动中和客户相关的条件是否符合
                c1 = pro.status != 1
                c2 = pro.first_order == 1 and not ShopOrders.query.filter_by(customer_id=customer.id, is_pay=1).first()
                c3 = not pro.customer_level <= customer.level
                c4 = pro.gender != 0 and pro.gender != customer.gender
                c5 = not datetime.timedelta(
                    days=pro.age_min // 4 + pro.age_min * 365
                ) <= datetime.datetime.now().date() - customer.birthday <= datetime.timedelta(
                    days=pro.age_max // 4 + pro.age_max * 365
                )
                c6 = sku_.special == 1 and pro.with_special == 0
                c7 = pro.scope == 1 if obj_ != 'global' else 0
                if c1 or c2 or c3 or c4 or c5 or c6 or c7:
                    # 剔除不满足条件的促销活动，一般用于scope=1的全局活动
                    if pro in the_promotions[obj_]['promotions']:
                        the_promotions[obj_]['promotions'].remove(pro)
                else:
                    # 将满足条件的促销活动添加到对应的结构体中
                    if pro not in the_promotions[obj_]['promotions']:
                        the_promotions[obj_]['promotions'].append(pro)

            the_promotions[obj_]['skus'].append(tmp)

        #
        for sku in args:
            sku_obj = SKU.query.get(sku['id'])
            pdict = {'sku': sku_obj,
                     'spu': sku_obj.the_spu,
                     'brand': sku_obj.the_spu.brand,
                     'classifies': sku_obj.the_spu.classifies,
                     'global': 'global'}
            for key, obj in pdict.items():
                _check_promotions(eval(key + '_promotions'), key, sku_obj, obj, sku)

        for s in ('sku', 'spu', 'brand', 'classifies', 'global'):
            for key, sp in eval(s + '_promotions').items():
                if sp.get('promotions'):
                    total_fee = sum([sku['sku'].price * sku['quantity'] for sku in sp['skus']])
                    total_quantity = sum([sku['quantity'] for sku in sp['skus']])
                    """排除掉冲突的促销活动"""
                    p_groups = defaultdict(list)
                    # 把非group 0的组和对应的促销活动归类，然后把非0的促销活动POP出来
                    pop_list = list()
                    for p in sp['promotions']:
                        if p.groups.group_id != 0:
                            # 判断促销活动本身是否有效
                            pop_list.append(p)
                            p_groups[p.groups].append(p)
                    for i in pop_list:
                        sp['promotions'].remove(i)

                    # 把非0的组进行排序，因为所有非0组都是互斥的，按照优先级排序得到最优组
                    gs = [g for g in p_groups.keys() if g.group_id != -1 and g.group_id != 0]
                    # 如果优先级相同，则随机取一个；所以在定义促销组的时候，应当检查优先级是否已存在，model中 unique=True
                    gs.sort(key=lambda x: x.priority)

                    # 把选举出来的非0组，追加到归类中，最终得到对应归类的有效的促销活动，下一步是判断范围内的sku的消费总额或者数量是否满足
                    if gs:
                        sp['promotions'].extend(p_groups[gs[0]])

                    # 判断用户属性及sku是否符合活动要求
                    pop_list = list()
                    for p in sp['promotions']:
                        # 所购商品是否满足利益表
                        total_fee = Decimal('0.00')
                        for sku in sp['skus']:
                            if sku.get('seckill_price'):
                                total_fee += sku.get('seckill_price') * sku['quantity']
                            else:
                                total_fee += sku.get('price') * sku['quantity']
                        total_quantity = sum([sku['quantity'] for sku in sp['skus']])
                        the_benefit = None
                        if p.accumulation == 0:
                            if p.promotion_type != 6 and p.benefits:
                                b = p.benefits[0]
                                if p.promotion_type in (0, 2, 3):
                                    if b.with_amount <= total_fee:
                                        the_benefit = b
                                elif p.promotion_type == 1:
                                    if (Decimal('0.00') < b.with_amount <= total_fee) or (
                                            Decimal("0.00") < b.with_quantity <= total_quantity):
                                        the_benefit = b

                            elif p.promotion_type == 6:
                                the_benefit = 6
                        # 可叠加，则找最后一个符合的
                        elif p.accumulation == 1:
                            for b in p.benefits:
                                if p.promotion_type in (0, 2, 3):
                                    if b.with_amount <= total_fee:
                                        the_benefit = b
                                elif p.promotion_type == 1:
                                    if b.with_amount <= total_fee or b.with_quantity <= total_quantity:
                                        the_benefit = b
                                else:
                                    break

                        if the_benefit is None:
                            pop_list.append(p)
                        else:
                            if not isinstance(sp.get('benefits'), list):
                                sp['benefits'] = list()
                            if the_benefit != 6:
                                sp['benefits'].append({p: the_benefit})
                    for p in pop_list:
                        sp['promotions'].remove(p)

            # 计算促销活动后的价格
            for k, v in eval(s + '_promotions').items():
                print(k, v)
                if v['promotions'] and v['benefits']:
                    for sku in v['skus']:
                        price = sku['seckill_price'] if sku.get('seckill_price') else sku['price']
                        v['order_price'] += price * sku['quantity']
                    for p, b in v['benefits'].items():
                        if p.promotion_type == 0:
                            v['order_price'] -= b.reduce_amount
                        elif p.promotion_type == 1:
                            pass
                        elif p.promotion_type == 2:
                            v['order_price'] *= b.discount_amount
                        elif p.promotion_type == 3:
                            pass
                        elif p.promotion_type == 4:
                            pass
                        elif p.promotion_type == 5:
                            pass
