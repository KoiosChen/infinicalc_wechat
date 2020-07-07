from . import db, logger
from .models import LoginInfo, Elements, ImgUrl, Brands, SPU, SKU, Standards, Classifies, StandardValue, \
    PurchaseInfo, Layout, SKULayout, SMSTemplate, SMSApp, Coupons, CouponReady, Customers, Roles, Users, Promotions, \
    Benefits, PromotionGroups, Gifts
from time import sleep
from sqlalchemy import or_, and_


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
            db.session.rollback()
            return False
    else:
        logger.debug(f">>> The line exist in {table} for {kwargs}")
        new_one = False
    return {'obj': __obj, 'status': new_one}


def table_fields(table, appends=[], removes=[]):
    original_fields = getattr(getattr(table, '__table__'), 'columns').keys()
    for a in appends:
        original_fields.append(a)
    for r in removes:
        original_fields.remove(r)
    return original_fields


def get_table_data(table, args, appends=[], removes=[]):
    page = args.get('page')
    current = args.get('current')
    size = args.get('size')
    search = args.get('search')
    and_fields_list = list()
    fields = table_fields(table, appends, removes)
    r = list()
    base_sql = table.query
    if page != 'true':
        if search:
            for k, v in search.items():
                if k in fields:
                    and_fields_list.append(getattr(getattr(table, k), 'contains')(v))
            table_data = base_sql.filter(and_(*and_fields_list)).all()
        else:
            table_data = base_sql.all()
    else:
        if search:
            for k, v in search.items():
                if k in fields:
                    and_fields_list.append(getattr(getattr(table, k), 'contains')(v))

            table_data = base_sql.filter(and_(*and_fields_list)).offset((current - 1) * size).limit(size).all()
        else:
            table_data = base_sql.offset((current - 1) * size).limit(size).all()

    page_len = len(table_data)

    def _make_data(data):
        rr = list()
        for t in data:
            tmp = dict()
            for f in fields:
                if f in ['create_at', 'update_at', 'price', 'member_price', 'discount', 'birthday']:
                    tmp[f] = str(getattr(t, f))
                elif f == 'roles':
                    tmp[f] = {role.id: role.name for role in t.roles}
                elif f == 'elements':
                    tmp[f] = [e.id for e in t.elements]
                elif f == 'children':
                    if t.children:
                        child_tmp = list()
                        for child in t.children:
                            child_tmp.extend(_make_data([child]))
                        tmp[f] = child_tmp
                else:
                    tmp[f] = getattr(t, f)

            rr.append(tmp)
        return rr

    r = _make_data(table_data)
    pop_list = list()
    for record in r:
        if record.get('parent_id'):
            pop_list.append(record)
    for p in pop_list:
        r.remove(p)
    return {"records": r, "total": page_len // size + 1, "size": size, "current": current} if page == 'true' else {
        "records": r}


def get_table_data_by_id(table, key_id, appends=[], removes=[]):
    fields = table_fields(table, appends, removes)
    t = table.query.get(key_id)
    tmp = dict()
    for f in fields:
        if f in ['create_at', 'update_at', 'price', 'member_price', 'discount', 'birthday']:
            tmp[f] = str(getattr(t, f))
        elif f == 'elements':
            tmp[f] = [e.id for e in t.elements]
        elif f == 'roles':
            tmp[f] = {r.id: r.name for r in t.roles}
        elif f == 'sku':
            tmp[f] = {s.id: s.name for s in t.sku.all()}
        elif f in ['values', 'images']:
            tmp1 = list()
            t1 = getattr(t, f)
            for value in t1:
                tmp1.append({'id': value.id, 'path': value.path, 'type': value.attribute})
            tmp[f] = tmp1
        else:
            tmp[f] = getattr(t, f)
    return tmp
