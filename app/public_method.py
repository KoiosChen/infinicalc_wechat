import json
import random
import threading
import uuid
from . import logger, db, redis_db, coupon_lock
from .common import false_return, submit_return, success_return, session_commit
from .models import *
from sqlalchemy import and_
import datetime
import traceback
from flask import session
from decimal import Decimal
from .models import Coupons, CouponReady

str_list = ['create_at', 'update_at', 'price', 'member_price', 'discount', 'birthday', 'seckill_price',
            'start_time', 'end_time', 'total_consumption', 'express_fee']


def format_decimal(num, zero_format="0.00", to_str=False):
    print(type(num))
    if isinstance(num, float) or isinstance(num, int) or isinstance(num, str):
        return str(num)
    else:
        formatted_ = num.quantize(Decimal(zero_format))
        if to_str:
            return str(formatted_)
        else:
            return formatted_


def new_data_obj(table, **kwargs):
    """
    创建新的数据对象
    :param table: 表名
    :param kwargs: 表数据，需要对应表字段
    :return: 新增，或者已有数据的对象
    """
    logger.debug(f">>> Check the {table} for data {kwargs}")
    __obj = eval(table).query.filter_by(**kwargs).first()
    new_one = True
    if not __obj:
        logger.debug(f">>> The table {table} does not have the obj, create new one!")
        try:
            __obj = eval(table)(**kwargs)
            db.session.add(__obj)
            db.session.flush()
        except Exception as e:
            logger.error(f'create {table} fail {kwargs} {e}')
            traceback.print_exc()
            db.session.rollback()
            return False
    else:
        logger.debug(f">>> The line exist in {table} for {kwargs}")
        new_one = False
    return {'obj': __obj, 'status': new_one}


def calc_sku_price(customer, table):
    member_card = customer.member_card.filter_by(status=1).first()
    if member_card:
        member_discount = member_card.discount if member_card.discount else Decimal('1.00')
        if table.member_price:
            total_price = table.member_price * member_discount
            return str(total_price.quantize(Decimal("0.00")))
        else:
            total_price = table.price * member_discount
            return str(total_price.quantize(Decimal("0.00")))
    else:
        discount = table.discount if table.discount else Decimal("1.00")
        total_price = table.price * discount
        return total_price.quantize(Decimal("0.00"))


def table_fields(table, appends=[], removes=[]):
    original_fields = getattr(getattr(table, '__table__'), 'columns').keys()
    for a in appends:
        original_fields.append(a)
    for r in removes:
        if r in original_fields:
            original_fields.remove(r)
    return original_fields


def find_id(elements_list):
    id_ = list()
    for el in elements_list:
        if el.get('children'):
            id_.extend(find_id(el['children']))
            id_.append(el['id'])
            return id_
        else:
            return [el['id']]


def __make_table(fields, table, strainer=None):
    tmp = dict()
    for f in fields:
        if f == 'elements':
            tmp[f] = [{"id": e.id, "name": e.name} for e in table.elements]
        elif f == 'roles':
            tmp[f] = [get_table_data_by_id(eval(role.__class__.__name__), role.id, ['elements']) for role in
                      table.roles]
        elif f == 'role':
            try:
                tmp[f] = {"id": table.role.id, "name": table.role.name}
            except Exception as e:
                logger.error(f"get role fail {e}")
                tmp[f] = {}
        elif f == 'menus':
            elements_list = table.elements
            elements_list_id = [elid.id for elid in elements_list]
            tmp[f] = list()
            exist_elements = list()
            for e in elements_list:
                if e.id not in exist_elements and e.type == 'menu' and e.parent_id is None:
                    tmp[f].append(
                        get_table_data_by_id(Elements, e.id, appends=['children'], strainer=['menu', elements_list_id]))
                    exist_elements.extend(find_id([tmp[f][-1]]))
        elif f == 'sku':
            tmp[f] = [get_table_data_by_id(eval(e.__class__.__name__), e.id, appends=['values', 'objects']) for e in
                      table.sku]
        elif f == 'spu':
            tmp[f] = [get_table_data_by_id(eval(e.__class__.__name__), e.id, appends=['sku', 'objects']) for e in
                      table.spu.all()]
        elif f == 'children':
            if table.children:
                child_tmp = list()
                for child in table.children:
                    if strainer is not None:
                        if child.type == strainer[0] and child.id in strainer[1]:
                            child_tmp.extend(_make_data([child], fields, strainer))
                    else:
                        child_tmp.extend(_make_data([child], fields, strainer))
                tmp[f] = child_tmp
        elif f == 'objects':
            tmp1 = list()
            t1 = getattr(table, f)
            for value in t1:
                if value.thumbnails:
                    tmp1.append({'id': value.id, 'url': value.url, 'obj_type': value.obj_type,
                                 'thumbnail': {'id': value.thumbnails[0].id,
                                               'url': value.thumbnails[0].url,
                                               'obj_type': value.thumbnails[0].obj_type}})
                else:
                    tmp1.append({'id': value.id, 'url': value.url, 'obj_type': value.obj_type})
            tmp1.sort(key=lambda x: x["obj_type"], reverse=True)
            tmp[f] = tmp1
        elif f == 'ad_image':
            t1 = getattr(table, f)
            tmp[f] = {'id': t1.id, 'url': t1.url, 'obj_type': t1.obj_type}
        elif f == 'values':
            tmp1 = list()
            t1 = getattr(table, f)
            for value in t1:
                tmp1.append({'value': value.value, 'standard_name': value.standards.name})
            tmp[f] = tmp1
        elif f == 'banner_contents' or f == 'news_cover_image':
            t1 = getattr(table, f)
            tmp[f] = {"id": t1.id, "type": t1.obj_type, "url": t1.url}
        elif f == 'brand':
            tmp[f] = get_table_data_by_id(Brands, table.brand.id)
        elif f == 'classifies':
            tmp[f] = get_table_data_by_id(Classifies, table.classifies.id)
        elif f == 'standards':
            if table.standards:
                tmp[f] = [{"id": e.id, "name": e.name} for e in table.standards]
            else:
                tmp[f] = []
        elif f == 'express_addresses':
            tmp[f] = [get_table_data_by_id(eval(e.__class__.__name__), e.id, [], ['sender', 'city_id', 'district']) for
                      e in
                      table.express_addresses.filter_by(status=1).all()]
        elif '_promotions' in f:
            tmp[f] = [{'id': p.id, 'name': p.name, 'type': p.promotion_type} for p in getattr(table, f) if
                      p.start_time <= datetime.datetime.now() <= p.end_time]
        elif f == 'gifts':
            tmp[f] = [get_table_data_by_id(SKU, g.sku, appends=['values', 'objects', 'sku_promotions']) for g in
                      table.gifts]
        elif f == 'news_section':
            tmp['section_name'] = table.news_section.name if table.news_section else ''
        elif f == 'real_price':
            customer = Customers.query.get(session['current_user'])
            if customer:
                tmp[f] = str(calc_sku_price(customer, table))
        elif f == 'items_orders':
            tmp[f] = list()
            for o in table.items_orders_id.all():
                sku_obj = o.bought_sku.objects
                sku_thumbnail = ''
                for obj in sku_obj:
                    if obj.obj_type == 0 and obj.thumbnails:
                        sku_thumbnail = obj.thumbnails[0].url
                        break
                sku_values = list()
                for v in o.bought_sku.values:
                    sku_values.append({'value': v.value, 'standard_name': v.standards.name})
                order_detail = {'sku_name': o.bought_sku.name,
                                'quantity': o.item_quantity,
                                'price': str(o.item_price),
                                'status': o.status,
                                'create_at': str(o.create_at),
                                'rates': o.rates,
                                'transaction_price': str(o.transaction_price),
                                'special': o.special,
                                'sku_thumbnail': sku_thumbnail,
                                'values': sku_values}
                tmp[f].append(order_detail)
        elif f == 'member_info':
            member_card_ = table.member_card.filter(MemberCards.status.__eq__(1)).first()
            if member_card_:
                tmp[f] = get_table_data_by_id(MemberCards, member_card_.id, removes=['update_at'])
            else:
                tmp[f] = {"member_type": 0}
        elif f == 'cargo_image':
            tmp[
                f] = "https://wine-1301791406.cos.ap-shanghai.myqcloud.com//ft/thumbnails/2680f646-8850-44c2-8360-700dcb908d2d.jpeg"
        elif f == 'my_invitees':
            tmp[f] = len(table.invitees)
        elif f == 'customer_info':
            tmp[f] = get_table_data_by_id(Customers, table.customer_id)
        elif f == 'coupon_brief':
            coupons_setting = table.coupon_setting
            with_amount = coupons_setting.promotion.benefits[0].with_amount
            reduced_amount = coupons_setting.promotion.benefits[0].reduced_amount
            name = coupons_setting.name
            desc = coupons_setting.desc
            if coupons_setting.valid_type == 1:
                start_at = table.take_at
                end_at = coupons_setting.absolute_date
            else:
                start_at = table.take_at
                end_at = table.take_at + datetime.timedelta(days=coupons_setting.valid_days)
            tmp[f] = {"name": name, "desc": desc, "with_amount": with_amount, "reduced_amount": reduced_amount,
                      "start_at": str(start_at), "end_at": str(end_at)}
        elif f == 'real_payed_cash_fee':
            coupon_reduce, card_reduce = order_payed_couponscards(table)
            tmp[f] = table.items_total_price - table.score_used - coupon_reduce - card_reduce
        else:
            r = getattr(table, f)
            if isinstance(r, int) or isinstance(r, float):
                tmp[f] = r
            elif r is None:
                tmp[f] = ''
            else:
                tmp[f] = str(r)
    return tmp


def _make_data(data, fields, strainer=None):
    rr = list()
    for t in data:
        rr.append(__make_table(fields, t, strainer))
    return rr


def _search(table, fields, search):
    and_fields_list = list()
    for k, v in search.items():
        if k in fields:
            if k in ('delete_at', 'used_at') and v is None:
                and_fields_list.append(getattr(getattr(table, k), '__eq__')(v))
            elif k in ('manager_customer_id', 'owner_id') and v:
                and_fields_list.append(getattr(getattr(table, k), '__eq__')(v))
            elif k in ('validity_at', 'end_at') and v is not None:
                and_fields_list.append(getattr(getattr(table, k), '__ge__')(v))
            elif k == 'start_at' and v is not None:
                and_fields_list.append(getattr(getattr(table, k), '__le__')(v))
            elif k == 'pay_at' and v == 'not None':
                and_fields_list.append(getattr(getattr(table, k), '__ne__')(None))
            else:
                and_fields_list.append(getattr(getattr(table, k), 'contains')(v))
    return and_fields_list


def _advance_search(table, fields, advance_search):
    and_fields_list = list()

    for search in advance_search:
        if search['key'] in fields:
            if '.' in search['key']:
                keys = search['key'].split('.')
                attr_key = getattr(getattr(table, keys[0]), keys[1])
            else:
                attr_key = getattr(table, search['key'])
            and_fields_list.append(getattr(attr_key, search['operator'])(search['value']))
    return and_fields_list


def get_table_data(table, args, appends=[], removes=[], advance_search=None, order_by=None):
    page = args.get('page')
    current = args.get('current')
    size = args.get('size')
    search = args.get('search')
    fields = table_fields(table, appends, removes)
    table_name = table.__name__
    if 'parent_id' in fields and table_name == 'Elements':
        base_sql = table.query.filter(table.parent_id.__eq__(None))
    else:
        base_sql = table.query

    if isinstance(current, int) and current <= 0:
        return False

    filter_args = list()
    if search:
        filter_args.extend(_search(table, fields, search))
        if advance_search is not None:
            filter_args.extend(_advance_search(table, fields, advance_search))
        search_sql = base_sql.filter(and_(*filter_args))
    else:
        if advance_search is not None:
            filter_args.extend(_advance_search(table, fields, advance_search))
            search_sql = base_sql.filter(and_(*filter_args))
        else:
            search_sql = base_sql

    if order_by is not None:
        search_sql = search_sql.order_by(getattr(getattr(table, order_by), "desc")())

    page_len = search_sql.count()
    if page != 'true':
        table_data = search_sql.all()
    else:
        if page_len < (current - 1) * size:
            current = 1
        table_data = search_sql.offset((current - 1) * size).limit(size).all()

    # if page != 'true':
    #     if search:
    #         filter_args = list()
    #         filter_args.extend(_search(table, fields, search))
    #         if advance_search is not None:
    #             filter_args.extend(_advance_search(table, fields, advance_search))
    #         table_data = base_sql.filter(and_(*filter_args)).all()
    #         page_len = len(table_data)
    #     else:
    #         table_data = base_sql.all()
    # else:
    #     if search:
    #         filter_args = list()
    #         filter_args.extend(_search(table, fields, search))
    #         if advance_search is not None:
    #             filter_args.extend(_advance_search(table, fields, advance_search))
    #         table_data = base_sql.filter(and_(*filter_args)).offset((current - 1) * size).limit(size).all()
    #         page_len = base_sql.filter(and_(*filter_args)).count()
    #     else:
    #         if current > 0:
    #             table_data = base_sql.offset((current - 1) * size).limit(size).all()
    #         else:
    #             return False

    r = _make_data(table_data, fields)

    if table.__name__ == 'Elements':
        pop_list = list()
        for record in r:
            if record.get('parent_id'):
                pop_list.append(record)
        for p in pop_list:
            r.remove(p)

    return {"records": r, "total": page_len, "size": size, "current": current} if page == 'true' else {"records": r}


def get_table_data_by_id(table, key_id, appends=[], removes=[], strainer=None, search=None, advance_search=None):
    fields = table_fields(table, appends, removes)
    base_sql = table.query
    if search is None and advance_search is None:
        t = base_sql.get(key_id)
    elif advance_search is not None:
        filter_args = _advance_search(table, fields, advance_search)
        filter_args.append(getattr(getattr(table, 'id'), '__eq__')(key_id))
        t = base_sql.filter(and_(*filter_args)).first()
    else:
        filter_args = _search(table, fields, search)
        filter_args.append(getattr(getattr(table, 'id'), '__eq__')(key_id))
        t = base_sql.filter(and_(*filter_args)).first()
    if t:
        return __make_table(fields, t, strainer)
    else:
        return {}


def create_member_card_by_invitation(current_user, invitation_code):
    member_card = current_user.member_card.first()

    # 此处目前仅支持邀请代理商
    if member_card and int(member_card.member_type) >= int(invitation_code.tobe_type) and int(
            member_card.grade) <= int(invitation_code.tobe_level):
        return false_return(message="当前用户已经是此级别(或更高级别），不可使用此邀请码"), 400

    if not member_card:
        card_no = create_member_card_num()
        new_member_card = new_data_obj("MemberCards", **{"card_no": card_no, "customer_id": current_user.id,
                                                         "open_date": datetime.datetime.now()})
    else:
        card_no = member_card.card_no
        new_member_card = {'obj': member_card, 'status': False}

    a = {"member_type": invitation_code.tobe_type,
         "grade": invitation_code.tobe_level,
         "validate_date": datetime.datetime.now() + datetime.timedelta(days=365)}

    for k, v in a.items():
        setattr(new_member_card['obj'], k, v)

    if new_member_card:
        if hasattr(invitation_code, "used_customer_id"):
            invitation_code.used_customer_id = current_user.id
        if hasattr(invitation_code, "new_member_card_id"):
            invitation_code.new_member_card_id = new_member_card['obj'].id
        if hasattr(invitation_code, "used_at"):
            invitation_code.used_at = datetime.datetime.now()
        if hasattr(invitation_code, "invitees"):
            invitation_code.invitees.append(new_member_card['obj'])

        current_user.invitor_id = invitation_code.manager_customer_id
        current_user.interest_id = invitation_code.interest_customer_id
        current_user.role_id = 2
        db.session.add(invitation_code)
        db.session.add(current_user)
    else:
        return false_return(message="邀请码有效，但是新增会员卡失败"), 400

    return submit_return(f"新增会员卡成功，卡号{card_no}, 会员级别{invitation_code.tobe_type} {invitation_code.tobe_level}",
                         "新增会员卡失败")


def create_member_card_num():
    today = datetime.datetime.now()
    return "5199" + str(today.year) + str(today.month).zfill(2) + str(today.day).zfill(2) + str(
        random.randint(1000, 9999))


def order_cancel(cancel_reason, shop_order_id):
    try:
        order = ShopOrders.query.get(shop_order_id)
        if not order:
            raise Exception(f"{shop_order_id} 不存在")
        elif order.is_pay == 1:
            raise Exception(f"当前支付状态不可取消")
        else:
            items = order.items_orders_id.all()
            # 恢复SKU数量
            for item in items:
                item.bought_sku.quantity += item.item_quantity
            order.delete_at = datetime.datetime.now()
            order.status = 0
            order.cancel_reason = cancel_reason
            order.consumer.total_points += order.score_used
        return submit_return("取消成功", "数据提交失败，取消失败")
    except Exception as e:
        return false_return(message=f"订单取消失败: {str(e)}"), 400


def take_coupon(coupon_id, take_coupon_id, user, lock):
    if lock.acquire():
        try:
            coupon_setting = Coupons.query.get(coupon_id)
            if coupon_setting:
                if coupon_setting.quota > 0:
                    already_take = CouponReady.query.filter_by(coupon_id=coupon_id, consumer=user).all()
                    if len(already_take) >= coupon_setting.per_user:
                        raise AttributeError(f"此用户已领优惠券<{coupon_id}>达到最大数量")
                    new_coupon = new_data_obj("CouponReady", **{"id": take_coupon_id, "coupon_id": coupon_id})
                    if new_coupon.get('status'):
                        coupon_setting.quota -= 1
                        coupon_setting.take_count += 1
                        new_coupon['obj'].consumer = user
                        redis_db.set(f"new_coupon::{take_coupon_id}",
                                     json.dumps(success_return(message="领取成功")),
                                     ex=6000) \
                            if session_commit() else \
                            redis_db.set(f"new_coupon::{take_coupon_id}",
                                         json.dumps(false_return(message=f"领取优惠券<{coupon_id}>失败")),
                                         ex=6000)

                    else:
                        redis_db.set(f"new_coupon::{take_coupon_id}", json.dumps(false_return(message=f"领取失败")),
                                     ex=6000)
                else:
                    redis_db.set(f"new_coupon::{take_coupon_id}",
                                 json.dumps(false_return(message=f'优惠券<{coupon_id}>已领完')), ex=6000)
            else:
                redis_db.set(f"new_coupon::{take_coupon_id}",
                             json.dumps(false_return(message=f"未找到优惠券设置<{coupon_id}>")), ex=6000)
        except Exception as e:
            logger.error(f"领取优惠券失败，因为{e}")
            redis_db.set(f"new_coupon::{take_coupon_id}", json.dumps(false_return(message=f"{e}")), ex=6000)
        finally:
            lock.release()


def query_coupon(**kwargs):
    take_coupon_id = str(uuid.uuid4())
    user = kwargs['current_user']
    coupon_thread = threading.Thread(target=take_coupon,
                                     args=(kwargs.get('coupon_id'), take_coupon_id, user.id, coupon_lock))
    coupon_thread.start()
    coupon_thread.join()
    k = f"new_coupon::{take_coupon_id}"
    if redis_db.exists(k):
        result = json.loads(redis_db.get(k))
        redis_db.delete(k)

        if result.get("code") == "success":
            return result
        else:
            return result, 400


def order_payed_couponscards(order):
    if not order:
        raise Exception(f"{order.id} 不存在")
    if order.coupon_used:
        coupon_reduce = order.coupon_used.coupon_setting.promotion.benefits[0].reduce_amount
    else:
        coupon_reduce = Decimal("0.00")

    if order.card_consumption:
        card_reduce = order.card_consumption.consumption_sum
    else:
        card_reduce = Decimal("0.00")

    return coupon_reduce, card_reduce
