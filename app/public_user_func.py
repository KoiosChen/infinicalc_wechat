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

def login():
    pass