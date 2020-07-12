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
                                       " 'combo': {'benefits_id': str, 'gifts':[gift_id]}}]"
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
            # 初始化 the_promotions
            for k in ('skus', 'promotions'):
                if not isinstance(the_promotions[obj_][k], list):
                    the_promotions[obj_][k] = list()
            price = sku_.price * sku_.discount if member_card is None else sku_.member_price * member_card.discount
            tmp = {"sku": sku_, "quantity": arg['quantity'], "price": price, "combo": arg.get('combo')}
            # 判断促销活动是否是秒杀
            if sku_.seckill_price:
                tmp['seckill_price'] = sku_.seckill_price

            if obj_ != 'global':
                # 获取对应obj_的所有促销活动
                promotions = getattr(obj_, key_ + '_promotions')
            else:
                promotions = the_promotions[obj_]['promotions']

            # 检查促销活动中和客户相关的条件是否符合
            for pro in promotions:
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

        # 用户前端加入购车，点击购物车后，进入购物车页面，从中获取每个SKU，并把SKU拆解到sku， spu， brand， classifies中，便于后面匹配促销活动
        for sku in args:
            # query SKU的数据库对象
            sku_obj = SKU.query.get(sku['id'])

            # 拆解sku
            pdict = {'sku': sku_obj,
                     'spu': sku_obj.the_spu,
                     'brand': sku_obj.the_spu.brand,
                     'classifies': sku_obj.the_spu.classifies,
                     'global': 'global'}

            # 按照拆解项来查询促销活动
            for key, obj in pdict.items():
                # 查询，将结果存放在如 sku_promotions 中
                _check_promotions(eval(key + '_promotions'), key, sku_obj, obj, sku)

        # 遍历key_promotions 字典
        for s in ('sku', 'spu', 'brand', 'classifies', 'global'):
            # 遍历其中每一项，排除掉冲突的活动
            for key, sp in eval(s + '_promotions').items():
                # 如果对应项有促销活动则进一步判断
                if sp.get('promotions') and sp['promotions'].promotion_type != 4:
                    # total_fee = sum([sku['sku'].price * sku['quantity'] for sku in sp['skus']])
                    # total_quantity = sum([sku['quantity'] for sku in sp['skus']])
                    """排除掉冲突的促销活动"""
                    p_groups = defaultdict(list)

                    # 把非group 0的组和对应的促销活动归类，然后把非0的促销活动POP出来
                    # 用来暂存需要pop的group
                    pop_list = list()
                    for p in sp['promotions']:
                        if p.groups.group_id != 0:
                            # 判断促销活动本身是否有效
                            pop_list.append(p)
                            # 对促销活动按照promotion group id 归类
                            p_groups[p.groups].append(p)
                    for pl in pop_list:
                        sp['promotions'].remove(pl)

                    # 把非0的组进行排序，因为所有非0组都是互斥的，按照优先级排序得到最优组
                    gs = [g for g in p_groups.keys() if g.group_id > 0]
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
                            # 判断是否是秒杀， 6是秒杀类型，并且存在利益表。如果不是秒杀并且没有利益表则跳过
                            if p.promotion_type != 6 and p.benefits:
                                # 因为不能累计，取利益表中的第一个，如果设置正确，其实也就只有一条利益表
                                b = p.benefits[0]

                                # '0: 满减，1：满赠，2：满折，3：加价购，4：套餐，5：预售, 6：秒杀, 7: 满减优惠券, 8: 满赠优惠券'
                                if p.promotion_type in (0, 2, 3):
                                    # 判断是否符合满减
                                    if b.with_amount <= total_fee:
                                        the_benefit = b
                                elif p.promotion_type == 1:
                                    # 这里要大于0， 是因为默认值为0， 如果等于零表示未设置则不判断
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
                            # 如果 the_benefit标签为None，则表示该促销活动不符合
                            pop_list.append(p)
                        else:
                            if not isinstance(sp.get('benefits'), list):
                                sp['benefits'] = list()
                            if the_benefit != 6:
                                sp['benefits'].append({p: the_benefit})
                    for pl in pop_list:
                        sp['promotions'].remove(pl)

            # 计算促销活动后的价格。购物车中的商品，针对不同的维度来计算最后的总价
            for k, v in eval(s + '_promotions').items():
                logger.debug(f"promotion {k}, content {v}")
                if v['promotions'] and v['benefits']:
                    # 计算正常（或含秒杀活动）的总价和总数
                    v['adjust_price'] = Decimal("0.00")
                    v['adjust_discount'] = Decimal("0.00")
                    for sku in v['skus']:
                        price = sku['seckill_price'] if sku.get('seckill_price') else sku['price']

                    # 计算促销活动后的价格
                    for p, b in v['benefits'].items():
                        if p.promotion_type == 0:
                            v['adjust_price'] -= b.reduce_amount
                        elif p.promotion_type == 1:
                            # 返回赠品清单
                            pass
                        elif p.promotion_type == 2:
                            v['adjust_discount'] *= b.discount_amount
                        elif p.promotion_type == 3:
                            # 返回加价购清单
                            pass
                        elif p.promotion_type == 4:
                            # 套餐不应该在此处计算，应该在下单的时候选择
                            pass
                        elif p.promotion_type == 5:
                            # 总价 - （预付款 * 倍数）
                            pass



