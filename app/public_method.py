from . import db, logger
from .models import LoginInfo, Elements, ImgUrl, Brands, SPU, SKU, Standards, Classifies, StandardValue, \
    PurchaseInfo, Layout, SKULayout, SMSTemplate, SMSApp, Coupons, CouponReady, Customers, Roles, Users, Promotions, \
    Benefits, PromotionGroups, Gifts
from time import sleep


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


def get_table_data(table, page, current, size, appends=[], removes=[]):
    fields = table_fields(table, appends, removes)
    r = list()
    if page == 'true':
        table_data = table.query.all()
    else:
        table_data = table.query.offset(current).limit(size)
    for t in table_data:
        tmp = dict()
        for f in fields:
            if f in ['create_at', 'update_at', 'price', 'member_price', 'discount']:
                tmp[f] = str(getattr(t, f))
            elif f == 'roles':
                tmp[f] = {r.id: r.name for r in t.roles}
            elif f == 'elements':
                tmp[f] = {e.id: e.name for e in t.elements}
            else:
                tmp[f] = getattr(t, f)
        r.append(tmp)
    return r


def get_table_data_by_id(table, key_id, appends=[], removes=[]):
    fields = table_fields(table, appends, removes)
    r = list()
    for t in table.query.get(key_id):
        tmp = dict()
        for f in fields:
            if f in ['create_at', 'update_at', 'price', 'member_price', 'discount']:
                tmp[f] = str(getattr(t, f))
            elif f == 'elements':
                tmp[f] = {e.id: e.name for e in t.elements}
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
        r.append(tmp)
    return r

