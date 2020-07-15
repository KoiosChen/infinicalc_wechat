from . import redis_db, db, logger
from .public_method import new_data_obj
from .common import success_return, false_return, session_commit
from .models import Roles, Users, Customers


def create_user(table_obj, **kwargs):
    phone = kwargs['phone']
    username = kwargs.get('username')
    password = kwargs.get('password')
    email = kwargs.get('email')
    role_ids = kwargs.get('role_id')
    new_user = new_data_obj(table_obj, **{"phone": phone, "status": 1})
    if new_user and new_user.get('status'):
        user = new_user['obj']
        if username:
            user.username = username
        if password:
            user.password = password
        if email:
            user.email = email
    else:
        return false_return(message=f"<{phone}>已经存在"), 400

    if not role_ids:
        role_ids = list()
        default_role = "normal_user" if table_obj == 'Users' else "normal_customer"
        role_ids.append(new_data_obj("Roles", **{"name": default_role})['obj'].id)

    for id_ in role_ids:
        user.roles.append(Roles.query.get(id_))
    db.session.add(user)
    if session_commit().get("code") == 'success':
        return_user = {
            'id': user.id,
            'phone': user.phone
        }
        return success_return(return_user, "用户注册成功")
    else:
        return false_return({}, '用户注册失败'), 400


def register(table_obj, **kwargs):
    key = f'back::verification_code::{kwargs["phone"]}'
    try:
        if redis_db.exists(key) and redis_db.get(key) == kwargs['verify_code']:
            return create_user(table_obj, **kwargs)
        else:
            return false_return(message='验证码错误'), 400
    except Exception as e:
        logger.error(f"{table_obj}::register::db_commit()::error --> {str(e)}")
        db.session.rollback()
        return false_return(data={}, message=str(e)), 400


def modify_user_profile(args, user, fields_):
    unique_list = ["username", "phone", "email"]
    user_class_name = user.__class__.__name__
    for f in fields_:
        if f == 'role_id' and args.get(f):
            user.roles = []
            for r in args.get(f):
                role = Roles.query.get(r)
                user.roles.append(role)
        elif args.get(f):
            u = eval(user_class_name)
            if f in unique_list:
                tmp = getattr(getattr(getattr(u, 'query'), "filter")(getattr(getattr(u, 'status'), '__eq__')(1),
                                                                     getattr(getattr(u, f), '__eq__')(args.get(f)),
                                                                     getattr(getattr(u, 'id'), '__ne__')(user.id)),
                              'first')()
                logger.debug(tmp)
                if not tmp:
                    setattr(user, f, args.get(f))
                else:
                    db.session.rollback()
                    return false_return(f"{f} 已存在"), 400
            else:
                setattr(user, f, args.get(f))
    if session_commit().get('code') == 'success':
        return success_return(message="更新成功")
    else:
        return false_return(message="更新失败")