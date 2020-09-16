from flask_restplus import Resource, reqparse
from ..models import SKU, ShopOrders, Promotions, Permission, ShoppingCart, Benefits, ExpressAddress, make_order_id, \
    PackingItemOrders
from .. import db, redis_db, default_api, logger
from ..common import success_return, false_return, session_commit, nesteddict, submit_return
from ..public_method import calc_sku_price
from ..decorators import permission_required
from ..swagger import return_dict, head_parser, page_parser
from app.type_validation import checkout_sku_type
from collections import defaultdict
import datetime
from decimal import Decimal
from sqlalchemy import and_, or_
from app.public_method import get_table_data_by_id
from app.wechat import pay

shopping_cart_ns = default_api.namespace('Shopping Cart', path='/shopping_cart', description='购物车API')

return_json = shopping_cart_ns.model('ReturnRegister', return_dict)

update_cart_parser = reqparse.RequestParser()
update_cart_parser.add_argument("quantity", help="需要更新的数量")
update_cart_parser.add_argument("combo", help="若更新，则传递新的benefit_id")

checkout_parser = reqparse.RequestParser()
checkout_parser.add_argument("shopping_cart_id", type=list, help='用户确认要购买的物品，传list，元素为shopping_cart_id',
                             location='json')

packing_checkout_parser = reqparse.RequestParser()
packing_checkout_parser.add_argument("packing_order", help='分装订单编号')

pay_parser = reqparse.RequestParser()
pay_parser.add_argument("score_used", type=int, help='使用的积分，1积分为1元')
pay_parser.add_argument("express_addr_id", type=str, help='express_address表id')
pay_parser.add_argument("message", type=str, help='用户留言')
pay_parser.add_argument("shopping_cart_id", type=list, help="传选中的shopping_cart表的id", location='json')
pay_parser.add_argument("packing_order", help='当在分装流程中，传递预分配的分装ID，不用传select_items；正常订单，只传select_items，不传packing_order')
pay_parser.add_argument("invoice_type", type=int, choices=[0, 1], help='0: 个人，1：企业')
pay_parser.add_argument("invoice_title", help='发票抬头， 如果invoice_type为1，显示此input框')
pay_parser.add_argument("invoice_tax_no", help="发票公司税号， 如果invoice_type为1，显示此input框")
pay_parser.add_argument("inovice_email", help="发票")

shopping_cart_parser = page_parser.copy()
shopping_cart_parser.add_argument('packing_order', help='若是分装流程，获取购物车页面需传递此参数; 否则不传，或者为空', location='args')


def checkout_cart(**args):
    express_addr = 0
    # 总的可用的积分数量
    total_score = 0
    total_price = Decimal("0.00")
    customer = args.pop('customer')
    shop_cart_ids = args['shopping_cart_id']
    for cart_id in shop_cart_ids:
        cart_obj = ShoppingCart.query.filter_by(id=cart_id, customer_id=customer.id).first()
        if not cart_obj or cart_obj.delete_at:
            raise Exception(f"用户ID<{customer.id}>无购物车id<{cart_id}>")

        sku = cart_obj.desire_skus
        if not sku or not sku.status or sku.delete_at:
            raise Exception(f"购物车id<{cart_id}>对应的sku不存在或已下架")

        if sku.need_express:
            express_addr = 1

        # 若可以使用积分，则取整sku价格，目前没有促销活动，只有price和member_price两种
        sku_price = calc_sku_price(customer, sku)
        if sku.score_type:
            total_score += int(sku.max_score) * cart_obj.quantity

        # 计算总价
        total_price += Decimal(sku_price) * cart_obj.quantity
    return total_price.quantize(Decimal("0.00")), total_score, express_addr


@shopping_cart_ns.route('/pay')
@shopping_cart_ns.expect(head_parser)
class Pay(Resource):
    @shopping_cart_ns.marshal_with(return_json)
    @shopping_cart_ns.doc(body=pay_parser)
    @permission_required(Permission.USER)
    def post(self, **kwargs):
        """点击支付后，提交此接口"""
        try:
            args = pay_parser.parse_args()
            addr = ExpressAddress.query.get(args.pop("express_addr_id"))
            args['express_address'] = str(addr.address1) + str(addr.address2)
            args['express_postcode'] = addr.postcode
            args['express_recipient'] = addr.recipient
            args['express_recipient_phone'] = addr.recipient_phone
            args['customer_id'] = kwargs['current_user'].id
            args['id'] = make_order_id()
            packing_order = args.get("packing_order")
            # 若是分装流程
            if packing_order:
                the_packing_order = PackingItemOrders.query.get(packing_order)
                the_packing_order.packing_at = datetime.datetime.now()
                args.pop("shopping_cart_id")
                select_items = [s.id for s in
                                ShoppingCart.query.filter_by(packing_item_order=args.get("packing_order")).all()]
                select_obj = ShoppingCart.query.filter_by(packing_item_order=args.pop("packing_order")).all()
                for si in select_obj:
                    if si.desire_skus.special == 32:
                        the_packing_order.consumption = Decimal(str(si.quantity)) * Decimal(str(0.5)) * Decimal(
                            str(0.9255))
                db.session.commit()

            else:
                select_items = args.pop('shopping_cart_id')

            for i in select_items:
                if ShoppingCart.query.get(i).delete_at:
                    raise Exception(f"购物车订单{i}已删除")
            total_price, total_score, express_addr = checkout_cart(
                **{"shopping_cart_id": select_items, 'customer': kwargs['current_user']})

            if args.get('score_used') and total_score < args['score_used']:
                raise Exception(f"欲使用积分{args['score_used']}此订单最大可消费积分为{total_score}")

            if not express_addr and addr:
                raise Exception("此订单货物都不可快递")

            args['items_total_price'] = total_price
            create_data = {'order_info': args, 'select_items': select_items, 'packing_order': packing_order}
            create_result = pay.create_order(**create_data)

            if create_result.get("code") == "false":
                return create_result
            out_trade_no = create_result.get("data")
            score_used = 0 if not args.get('score_used') else args.get('score_used')
            return pay.weixin_pay(out_trade_no=out_trade_no, price=total_price - score_used,
                                  openid=kwargs['current_user'].openid)

        except Exception as e:
            return false_return(message=str(e)), 400


@shopping_cart_ns.route('/checkout')
@shopping_cart_ns.expect(head_parser)
class CheckOut(Resource):
    @shopping_cart_ns.marshal_with(return_json)
    @shopping_cart_ns.doc(body=checkout_parser)
    @permission_required(Permission.USER)
    def post(self, **kwargs):
        """点击 ‘去结算’ 计算可用积分总数及总价，进入结算页"""
        args = checkout_parser.parse_args()
        args['customer'] = kwargs['current_user']
        try:
            total_price, total_score, express_addr = checkout_cart(**args)
            sku = list()
            for cart_id in args['shopping_cart_id']:
                cart = ShoppingCart.query.filter_by(id=cart_id, customer_id=kwargs.get('current_user').id).first()
                the_sku = get_table_data_by_id(SKU, cart.sku_id, ['values', 'objects', 'real_price'],
                                               ['price', 'member_price', 'discount', 'content', 'seckill_price',
                                                'score_type', 'max_score'])
                the_sku['quantity'] = cart.quantity
                the_sku['shopping_cart_id'] = cart_id
                sku.append(the_sku)
            return success_return(
                {"total_score": str(total_score),
                 "total_price": str(total_price),
                 "express_addr": express_addr,
                 "sku": sku},
                'express_addr为0，表示此订单中没有需要快递的商品')
        except Exception as e:
            return false_return(message=str(e)), 400


@shopping_cart_ns.route('/packing_checkout')
@shopping_cart_ns.expect(head_parser)
class PackingCheckOut(Resource):
    @shopping_cart_ns.marshal_with(return_json)
    @shopping_cart_ns.doc(body=packing_checkout_parser)
    @permission_required(Permission.USER)
    def post(self, **kwargs):
        """分装流程，最后点击 ‘去结算’ 计算可用积分总数及总价，进入结算页"""
        args = packing_checkout_parser.parse_args()
        args['customer'] = kwargs['current_user']
        packing_order_id = args.pop('packing_order')
        args['shopping_cart_id'] = [sc.id for sc in
                                    ShoppingCart.query.filter_by(packing_item_order=packing_order_id).all()]
        try:
            total_price, total_score, express_addr = checkout_cart(**args)
            sku = list()
            for cart_id in args['shopping_cart_id']:
                cart = ShoppingCart.query.filter_by(id=cart_id, customer_id=kwargs.get('current_user').id).first()
                the_sku = get_table_data_by_id(SKU, cart.sku_id, ['values', 'objects', 'real_price'],
                                               ['price', 'member_price', 'discount', 'content', 'seckill_price',
                                                'score_type', 'max_score'])
                the_sku['quantity'] = cart.quantity
                the_sku['shopping_cart_id'] = cart_id
                sku.append(the_sku)
            return success_return(
                {"total_score": total_score,
                 "total_price": str(total_price.quantize(Decimal("0.00"))),
                 "express_addr": express_addr,
                 "sku": sku},
                'express_addr为0，表示此订单中没有需要快递的商品')
        except Exception as e:
            return false_return(message=str(e)), 400


@shopping_cart_ns.route('/<string:shopping_cart_id>')
@shopping_cart_ns.expect(head_parser)
class UpdateShoppingCart(Resource):
    @shopping_cart_ns.marshal_with(return_json)
    @shopping_cart_ns.doc(body=update_cart_parser)
    @permission_required(Permission.USER)
    def put(self, **kwargs):
        """在购物车页面修改商品数量"""
        args = update_cart_parser.parse_args()
        try:
            customer = kwargs['current_user']
            shopping_cart_item = ShoppingCart.query.filter(ShoppingCart.customer_id.__eq__(customer.id),
                                                           ShoppingCart.status.__eq__(1),
                                                           ShoppingCart.id.__eq__(kwargs['shopping_cart_id']),
                                                           ShoppingCart.delete_at.__eq__(None)).first()
            if not shopping_cart_item:
                raise Exception(f"{kwargs['shopping_cart_id']} 不存在")
            sku = SKU.query.get(shopping_cart_item.sku_id)

            if not sku or sku.delete_at or not sku.status:
                raise Exception(f"购物车对应SKU异常")

            if 'quantity' in args.keys() and args['quantity']:
                if isinstance(args['quantity'], str):
                    quantity = int(args['quantity'])
                else:
                    quantity = args['quantity']
                if quantity > sku.quantity:
                    raise Exception("所需购买数量大于库存")
                shopping_cart_item.quantity = args['quantity']

            if "combo" in args.keys() and args['combo']:
                shopping_cart_item.combo = args['combo']

            db.session.add(shopping_cart_item)
            return submit_return(f"更新{kwargs['shopping_cart_id']}成功", f"更新{kwargs['shopping_cart_id']} 数据提交失败")
        except Exception as e:
            return false_return(message=str(e)), 400

    @shopping_cart_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def delete(self, **kwargs):
        """删除购物车中该商品"""
        try:
            customer = kwargs['current_user']
            to_be_deleted = ShoppingCart.query.filter(ShoppingCart.customer_id.__eq__(customer.id),
                                                      ShoppingCart.status.__eq__(1),
                                                      ShoppingCart.id.__eq__(kwargs['shopping_cart_id']),
                                                      ShoppingCart.delete_at.__eq__(None)).first()
            if not to_be_deleted:
                raise Exception("购物车中无此商品")

            to_be_deleted.delete_at = datetime.datetime.now()
            db.session.add(to_be_deleted)
            return submit_return("删除成功", "删除时数据提交失败")
        except Exception as e:
            return false_return(message=str(e)), 200


@shopping_cart_ns.route('')
@shopping_cart_ns.expect(head_parser)
class ShoppingCartApi(Resource):
    @shopping_cart_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def delete(self, **kwargs):
        """清空购物车"""
        try:
            customer = kwargs['current_user']
            desired_items = customer.shopping_cart.filter(ShoppingCart.status.__eq__(1),
                                                          ShoppingCart.delete_at.__eq__(None)).all()
            for i in desired_items:
                i.delete_at = datetime.datetime.now()
                db.session.add(i)
            return submit_return("清空成功", "清空时数据提交失败")
        except Exception as e:
            return false_return(message=str(e)), 200

    @shopping_cart_ns.marshal_with(return_json)
    @permission_required(Permission.USER)
    def get(self, **kwargs):
        """显示购物车（不显示分装过程中的零时购物车内容），目前只有套餐一种促销活动，结果返回sku的list，包括价格、数量、总价、选择的套餐"""

        def _check_promotions(the_promotions, key_, sku_, obj_, arg):
            """
            根据sku， spu， brand， classify归类促销活动
            :param key_: str， 与 _promotions 组成变量名
            :param sku_: sku 数据库对象
            :param obj_: 对应key的数据库对象
            :return:
            """
            for k in ('skus', 'promotions'):
                if not isinstance(the_promotions[obj_][k], list):
                    the_promotions[obj_][k] = list()

            # 如果有套餐，则按照套餐价格计算
            if arg.get('combo'):
                combo_benefit = Benefits.query.get(arg.get('combo'))
                price = combo_benefit.combo_price

            # 如果没有会员折扣，按照原价计算
            else:
                price = calc_sku_price(customer, sku_)

            tmp = {"sku": sku_, "shopping_cart_id": arg['shopping_cart_id'], "quantity": arg['quantity'],
                   "price": price, "combo": arg.get('combo')}
            # 判断促销活动是否是秒杀
            if sku_.seckill_price:
                tmp['seckill_price'] = sku_.seckill_price

            if obj_ != 'global':
                # 20200725 需要修改，不比较套餐 优惠券活动
                promotions = getattr(obj_, key_ + '_promotions')
                if promotions:
                    promotions = [promotion_ for promotion_ in promotions if promotion_.promotion_type not in (4, 7, 8)]
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

        try:
            all_p = defaultdict(list)
            customer = kwargs['current_user']
            params = shopping_cart_parser.parse_args()
            packing_order = params.get("packing_order") if params.get("packing_order") else None
            args = [{'id': c.sku_id, 'shopping_cart_id': c.id, 'quantity': c.quantity, 'combo': c.combo} for c in
                    customer.shopping_cart.filter(ShoppingCart.delete_at.__eq__(None),
                                                  ShoppingCart.status.__eq__(1),
                                                  ShoppingCart.packing_item_order.__eq__(packing_order)).all()]
            member_card = None
            member_cards = customer.member_card
            for card in member_cards:
                if card and card.status == 1:
                    member_card = card
            classifies_promotions = nesteddict()
            brand_promotions = nesteddict()
            spu_promotions = nesteddict()
            sku_promotions = nesteddict()
            global_promotions = {"global": {
                "skus": [],
                "promotions": Promotions.query.filter(Promotions.scope == 1,
                                                      Promotions.status == 1,
                                                      and_(Promotions.promotion_type != 4,
                                                           Promotions.promotion_type != 7,
                                                           Promotions.promotion_type != 8)).all()}
            }

            #
            for sku in args:
                sku_obj = SKU.query.get(sku['id'])

                # 活动字典 promotion dict
                pdict = {'sku': sku_obj,
                         'spu': sku_obj.the_spu,
                         'brand': sku_obj.the_spu.brand,
                         'classifies': sku_obj.the_spu.classifies,
                         'global': 'global'}

                # 检查这个SKU 及对应的SPU 分类 品牌 或者全局是否有活动
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

            return_result = list()
            for skus in sku_promotions.values():
                for sku in skus['skus']:
                    total_price = Decimal(sku['price']) * sku['quantity']
                    return_result.append(
                        {"sku": get_table_data_by_id(SKU, sku['sku'].id,
                                                     appends=['values', 'objects', 'sku_promotions'],
                                                     removes=['price', 'seckill_price', 'member_price', 'discount']),
                         "shopping_cart_id": sku['shopping_cart_id'],
                         "quantity": sku['quantity'],
                         'price': str(sku['price']),
                         'total_price': str(total_price.quantize(Decimal("0.00"))),
                         'combo': get_table_data_by_id(Benefits, sku['combo'], appends=['gifts'])})
            return success_return(data=return_result)
        except Exception as e:
            return false_return(message=str(e)), 400
