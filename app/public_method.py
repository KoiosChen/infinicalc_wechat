from . import db, logger
from .models import LoginInfo, Elements, ImgUrl, Brands, SPU, SKU, Standards, Classifies, StandardValue, \
    PurchaseInfo, Layout, SKULayout, SMSTemplate, SMSApp, Coupons, CouponReady, Customers, Roles, Users, Promotions, \
    Benefits, PromotionGroups, Gifts, ObjStorage, Banners
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
        if r in original_fields:
            original_fields.remove(r)
    return original_fields


def _make_data(data, fields, strainer=None):
    rr = list()
    for t in data:
        tmp = dict()
        for f in fields:
            if f in ['create_at', 'update_at', 'price', 'member_price', 'discount', 'birthday', 'seckill_price',
                     'start_time', 'end_time']:
                tmp[f] = str(getattr(t, f))
            elif f == 'roles':
                tmp[f] = [{"id": role.id, "name": role.name} for role in t.roles]
            elif f == 'elements':
                tmp[f] = [{"id": e.id, "name": e.name} for e in t.elements]
            elif f == 'sku':
                tmp[f] = [{"id": e.id, "name": e.name} for e in t.sku]
            elif f == 'children':
                if t.children:
                    child_tmp = list()
                    for child in t.children:
                        if strainer is not None:
                            if child.type == strainer[0] and child.id in strainer[1]:
                                child_tmp.extend(_make_data([child], fields, strainer))
                        else:
                            child_tmp.extend(_make_data([child], fields, strainer))
                    tmp[f] = child_tmp
            elif f == 'images':
                tmp1 = list()
                t1 = getattr(t, f)
                for value in t1:
                    tmp1.append({'id': value.id, 'path': value.path, 'type': value.attribute})
                tmp[f] = tmp1
            elif f == 'values':
                tmp1 = list()
                t1 = getattr(t, f)
                for value in t1:
                    tmp1.append({'value': value.value, 'standard_name': value.standards.name})
                tmp[f] = tmp1
            elif f == 'banner_contents':
                t1 = getattr(t, f)
                tmp[f] = {"id": t1.id, "type": t1.obj_type, "url": t1.url}
            else:
                tmp[f] = getattr(t, f)

        rr.append(tmp)
    return rr


def get_table_data(table, args, appends=[], removes=[]):
    page = args.get('page')
    current = args.get('current')
    size = args.get('size')
    search = args.get('search')
    and_fields_list = list()
    fields = table_fields(table, appends, removes)
    r = list()
    if 'parent_id' in fields:
        base_sql = table.query.filter(table.parent_id.__eq__(None))
    else:
        base_sql = table.query

    page_len = len(base_sql.all())

    if page != 'true':
        if search:
            for k, v in search.items():
                if k in fields:
                    and_fields_list.append(getattr(getattr(table, k), 'contains')(v))
            table_data = base_sql.filter(and_(*and_fields_list)).all()
        else:
            table_data = base_sql.all()
    else:
        # page_more = 1 if page_len % size else 0
        if search:
            for k, v in search.items():
                if k in fields:
                    and_fields_list.append(getattr(getattr(table, k), 'contains')(v))

            table_data = base_sql.filter(and_(*and_fields_list)).offset((current - 1) * size).limit(size).all()
        else:
            if current > 0:
                table_data = base_sql.offset((current - 1) * size).limit(size).all()
            else:
                return False

    r = _make_data(table_data, fields)
    pop_list = list()
    for record in r:
        if record.get('parent_id'):
            pop_list.append(record)
    for p in pop_list:
        r.remove(p)

    return {"records": r, "total": page_len, "size": size, "current": current} if page == 'true' else {"records": r}


def get_table_data_by_id(table, key_id, appends=[], removes=[], strainer=None):
    fields = table_fields(table, appends, removes)
    t = table.query.get(key_id)
    tmp = dict()

    def find_id(elements_list):
        id_ = list()
        for el in elements_list:
            if el.get('children'):
                id_.extend(find_id(el['children']))
                id_.append(el['id'])
                return id_
            else:
                return [el['id']]

    for f in fields:
        if f in ['create_at', 'update_at', 'price', 'member_price', 'discount', 'birthday', 'seckill_price',
                 'start_time', 'end_time', 'total_consumption']:
            tmp[f] = str(getattr(t, f))
        elif f == 'elements':
            tmp[f] = [{"id": e.id, "name": e.name} for e in t.elements]
        elif f == 'menus':
            elements_list = t.elements
            elements_list_id = [elid.id for elid in elements_list]
            tmp[f] = list()
            exist_elements = list()
            for e in elements_list:
                if e.id not in exist_elements and e.type == 'menu' and e.parent_id is None:
                    tmp[f].append(
                        get_table_data_by_id(Elements, e.id, appends=['children'], strainer=['menu', elements_list_id]))
                    exist_elements.extend(find_id([tmp[f][-1]]))

        elif f == 'roles':
            tmp[f] = [{"id": role.id, "name": role.name} for role in t.roles]
        elif f == 'role':
            try:
                tmp[f] = {"id": t.role.id, "name": t.role.name}
            except Exception as e:
                logger.error(f"get role fail {e}")
                tmp[f] = {}
        elif f == 'sku':
            tmp[f] = [{"id": s.id, "name": s.name} for s in t.sku.all()]
        elif f == 'images':
            tmp1 = list()
            t1 = getattr(t, f)
            for value in t1:
                tmp1.append({'id': value.id, 'path': value.path, 'type': value.attribute})
            tmp[f] = tmp1
        elif f == 'children':
            if t.children:
                child_tmp = list()
                for child in t.children:
                    if strainer is not None:
                        if child.type == strainer[0] and child.id in strainer[1]:
                            child_tmp.extend(_make_data([child], fields, strainer))
                    else:
                        child_tmp.extend(_make_data([child], fields, strainer))
                tmp[f] = child_tmp
        elif f == 'values':
            tmp1 = list()
            t1 = getattr(t, f)
            for value in t1:
                tmp1.append({'value': value.value, 'standard_name': value.standards.name})
            tmp[f] = tmp1
        elif f == 'banner_contents':
            t1 = getattr(t, f)
            tmp[f] = {"id": t1.id, "type": t1.obj_type, "url": t1.url}
        else:
            tmp[f] = getattr(t, f)
    return tmp
