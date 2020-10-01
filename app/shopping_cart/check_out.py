from decimal import Decimal
from app.models import ShoppingCart, SKU
from app.public_method import calc_sku_price
from app.common import success_return, false_return
from app.public_method import get_table_data_by_id
from app import logger
import datetime
from collections import defaultdict
import traceback


def checkout_cart(**args):
    express_addr = 0
    # 总的可用的积分数量
    total_score = 0
    total_price = Decimal("0.00")
    customer = args.pop('customer')
    shop_cart_ids = args['shopping_cart_id']
    sku_statistic = defaultdict(dict)
    for cart_id in shop_cart_ids:
        cart_obj = ShoppingCart.query.filter_by(id=cart_id, customer_id=customer.id).first()
        if not cart_obj or cart_obj.delete_at:
            raise Exception(f"用户ID<{customer.id}>无购物车id<{cart_id}>")

        sku = cart_obj.desire_sku
        if not sku or not sku.status or sku.delete_at:
            raise Exception(f"购物车id<{cart_id}>对应的sku不存在或已下架")

        if sku.need_express:
            express_addr = 1

        # 若可以使用积分，则取整sku价格，目前没有促销活动，只有price和member_price两种
        sku_price = calc_sku_price(customer, sku)
        if sku.score_type:
            total_score += int(sku.max_score) * cart_obj.quantity

        # 记录每个SKU的总价，后续可用于计算促销活动是否满足要求
        sku_statistic[sku.id] = {"total_price": Decimal(sku_price) * cart_obj.quantity, "quantity": cart_obj.quantity}
        # 计算总价
        total_price += Decimal(sku_price) * cart_obj.quantity

    return total_price.quantize(Decimal("0.00")), total_score, express_addr, sku_statistic


def check_promotions_base_police(customer, sku):
    """
    目前仅检测促销活动中满减券的结果
    :param customer:
    :param sku:
    :return:
    """
    coupons = list()
    reject_score_flag = 0
    force_use_coupon = 0
    for pro in sku.sku_promotions:
        if pro.promotion_type == 7:
            # 检查促销活动中和客户相关的条件是否符合
            c1 = pro.status != 1
            c2 = pro.first_order == 1 and customer.orders.filter_by(is_pay=1).first()
            c3 = not pro.customer_level <= customer.level
            c4 = pro.gender != 0 and pro.gender != customer.gender
            c5 = not datetime.timedelta(
                days=pro.age_min // 4 + pro.age_min * 365
            ) <= datetime.datetime.now().date() - customer.birthday <= datetime.timedelta(
                days=pro.age_max // 4 + pro.age_max * 365
            )
            c6 = sku.special > 0 and pro.with_special == 0
            if c1 or c2 or c3 or c4 or c5 or c6:
                # 剔除不满足条件的促销活动，一般用于scope=1的全局活动
                logger.debug("当前用户不满足活动条件")
            else:
                if pro.coupon.status != 1:
                    # 去除状态异常的优惠券
                    continue
                if pro.coupon.valid_type == 1 and pro.coupon.absolute_date:
                    # 如果优惠券类型是绝对时间，那么判断当前时间是否超过绝对到期时间
                    if not datetime.datetime.now() < pro.coupon.absolute_date:
                        continue
                # 将有效的优惠券设置，添加到coupons列表中
                coupons.append(pro.coupon_id)

                if pro.reject_score:
                    # 如果活动与积分互斥，则如果使用此活动，则不能使用积分
                    reject_score_flag = 1

                if pro.first_order == 1 and not customer.orders.filter_by(is_pay=1).first():
                    # 如果活动是只有首单参与，并且用户未有付款订单，那么就强制在支付额时候使用优惠券
                    force_use_coupon = 1
    # 返回满足基本策略的可用的优惠券id；是否有优惠券和积分冲突；强制使用优惠券，目前当优惠券为首单满减，那么就强制使用优惠券
    return coupons, reject_score_flag, force_use_coupon


def check_out(args, kwargs):
    customer = args['customer']
    try:
        total_price, total_score, express_addr, sku_statistic = checkout_cart(**args)
        sku = list()
        reject_score_flag = 0
        force_use_coupon = 0
        could_use_coupons = defaultdict(list)
        for cart_id in args['shopping_cart_id']:
            cart = ShoppingCart.query.filter_by(id=cart_id, customer_id=kwargs.get('current_user').id).first()

            # desire_sku_promotions = sku_.sku_promotions
            # 获取购物车中sku的详情
            the_sku = get_table_data_by_id(SKU, cart.sku_id, ['values', 'objects', 'real_price'],
                                           ['price', 'member_price', 'discount', 'content', 'seckill_price'])

            # 检索sku对应的促销活动，查找使用其中的优惠券
            sku_ = cart.desire_sku
            base_coupons, reject_score_flag, force_use_coupon = check_promotions_base_police(kwargs.get('current_user'),
                                                                                             sku_)
            if sku_.id not in could_use_coupons.keys():
                could_use_coupons[sku_.id] = list()

            # 检查用户所有领取的优惠券是否在有效优惠券活动中
            for customer_coupon in customer.coupons.filter_by(status=1).all():
                coupons_setting = customer_coupon.coupon_setting
                if customer_coupon.coupon_id in base_coupons:
                    if customer_coupon.coupon_setting.valid_type == 1:
                        # 如果是相对时间有效，计算当前日期减去领取日期是否大于有效天数
                        if not datetime.datetime.now() - customer_coupon.take_at > datetime.timedelta(
                                days=customer_coupon.coupon_setting.valid_days):
                            continue
                    if cart.quantity * Decimal(the_sku['real_price']) >= coupons_setting.promotion.benefits[
                        0].with_amount:
                        could_use_coupons[coupons_setting.promotion.sku[0].id].append({"name": coupons_setting.name,
                                                                                       "desc": coupons_setting.desc,
                                                                                       "coupon_id": customer_coupon.id,
                                                                                       "for_item":
                                                                                           coupons_setting.promotion.sku[
                                                                                               0].id,
                                                                                       "with_amount":
                                                                                           coupons_setting.promotion.benefits[
                                                                                               0].with_amount,
                                                                                       "reduced_amount":
                                                                                           coupons_setting.promotion.benefits[
                                                                                               0].reduced_amount})
            the_sku['quantity'] = cart.quantity
            the_sku['shopping_cart_id'] = cart_id
            sku.append(the_sku)
        return success_return(
            {"total_score": total_score if force_use_coupon == 0 else 0,
             "reject_score_flag": reject_score_flag,
             "force_use_coupon": force_use_coupon,
             "total_price": str(total_price.quantize(Decimal("0.00"))),
             "express_addr": express_addr,
             "sku": sku,
             "coupons": could_use_coupons},
            'express_addr为0，表示此订单中没有需要快递的商品')
    except Exception as e:
        traceback.print_exc()
        return false_return(message=str(e)), 400
