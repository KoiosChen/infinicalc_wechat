from . import db, logger
from .models import *
from time import sleep
from sqlalchemy import or_, and_
import datetime

str_list = ['create_at', 'update_at', 'price', 'member_price', 'discount', 'birthday', 'seckill_price',
            'start_time', 'end_time', 'total_consumption', 'express_fee']


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
                        get_table_data_by_id(Elements, e.id, appends=['children'],
                                             strainer=['menu', elements_list_id]))
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
                    tmp1.append({'id': value.id, 'url': value.login_url, 'obj_type': value.obj_type,
                                 'thumbnail': {'id': value.thumbnails[0].id,
                                               'url': value.thumbnails[0].login_url,
                                               'obj_type': value.thumbnails[0].obj_type}})
                else:
                    tmp1.append({'id': value.id, 'url': value.login_url, 'obj_type': value.obj_type})
            tmp[f] = tmp1
        elif f == 'values':
            tmp1 = list()
            t1 = getattr(table, f)
            for value in t1:
                tmp1.append({'value': value.value, 'standard_name': value.standards.name})
            tmp[f] = tmp1
        elif f == 'banner_contents':
            t1 = getattr(table, f)
            tmp[f] = {"id": t1.id, "type": t1.obj_type, "url": t1.login_url}
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
                      table.express_addresses.all()]
        elif '_promotions' in f:
            tmp[f] = [{'id': p.id, 'name': p.name, 'type': p.promotion_type} for p in getattr(table, f) if
                      p.start_time <= datetime.datetime.now() <= p.end_time]
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
    return __make_table(fields, t, strainer)
