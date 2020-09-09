from . import logger
from .models import *
from sqlalchemy import and_
import datetime
import traceback
from flask import session
from decimal import Decimal

str_list = ['create_at', 'update_at', 'price', 'member_price', 'discount', 'birthday', 'seckill_price',
            'start_time', 'end_time', 'total_consumption', 'express_fee']


def format_decimal(num, zero_format="0.00", to_str=False):
    print(type(num))
    if isinstance(num, float) or isinstance(num, int) or isinstance(num, str):
        return str(num)
    else:
        formatted_ = num.quantize(Decimal(zero_format))
        if to_str:
            return str(num)
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
            tmp[f] = tmp1
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
                tmp[f].append(get_table_data_by_id(ItemsOrders, o.id))
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
            elif k in ('manager_customer_id') and v:
                and_fields_list.append(getattr(getattr(table, k), '__eq__')(v))
            elif k == 'validity_at' and v is not None:
                and_fields_list.append(getattr(getattr(table, k), '__ge__')(v))
            else:
                and_fields_list.append(getattr(getattr(table, k), 'contains')(v))
    return and_fields_list


def get_table_data(table, args, appends=[], removes=[]):
    page = args.get('page')
    current = args.get('current')
    size = args.get('size')
    search = args.get('search')
    fields = table_fields(table, appends, removes)
    r = list()
    table_name = table.__name__
    if 'parent_id' in fields and table_name == 'Elements':
        base_sql = table.query.filter(table.parent_id.__eq__(None))
    else:
        base_sql = table.query

    page_len = len(base_sql.all())

    if page != 'true':
        if search:
            table_data = base_sql.filter(and_(*_search(table, fields, search))).all()
        else:
            table_data = base_sql.all()
    else:
        if search:
            table_data = base_sql.filter(and_(*_search(table, fields, search))).offset((current - 1) * size).limit(
                size).all()
        else:
            if current > 0:
                table_data = base_sql.offset((current - 1) * size).limit(size).all()
            else:
                return False

    r = _make_data(table_data, fields)

    if table.__name__ == 'Elements':
        pop_list = list()
        for record in r:
            if record.get('parent_id'):
                pop_list.append(record)
        for p in pop_list:
            r.remove(p)

    return {"records": r, "total": page_len, "size": size, "current": current} if page == 'true' else {"records": r}


def get_table_data_by_id(table, key_id, appends=[], removes=[], strainer=None, search=None):
    fields = table_fields(table, appends, removes)
    base_sql = table.query
    if search is None:
        t = base_sql.get(key_id)
    else:
        t = base_sql.filter(and_(*_search(table, fields, search))).first()
    if t:
        return __make_table(fields, t, strainer)
    else:
        return {}
