from functools import wraps
from flask import abort, request, jsonify
from .models import Permissions
from . import logger
from .common import success_return, false_return
from app.auth.auths import identify
from app.frontstage_auth import auths


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        logger.info(
            'IP {} is checking login status'.format(
                request.headers.get('X-Forwarded-For', request.remote_addr)))
        if not identify(request).get('code') == "success":
            abort(jsonify(false_return(message='用户未登陆')))
        return f(*args, **kwargs)

    return decorated_function


def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 区分前后台
            if permission.split('.')[0] == 'frontstage':
                current_user = auths.identify(request)
            else:
                current_user = identify(request)

            if current_user.get('code') == 'success' and 'logout' in permission:
                kwargs['info'] = current_user['data']
                return f(*args, **kwargs)

            if current_user.get("code") == "success" and "admin" not in [r.name for r in
                                                                         current_user['data']['user'].roles]:
                if permission not in [p.action for p in current_user['data']['user'].permissions]:
                    logger.warn('This user\'s action is not permitted!')
                    abort(403, false_return(message='This user\'s action is not permitted!'))
            elif current_user.get("code") == "success" and "admin" in [r.name for r in
                                                                       current_user['data']['user'].roles]:
                pass
            else:
                abort(403, current_user)
            kwargs['info'] = current_user['data']
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def permission_ip(permission_ip_list):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            logger.info(
                'IP {} is trying to get the api'.format(
                    request.headers.get('X-Forwarded-For', request.remote_addr)))
            if request.headers.get('X-Forwarded-For', request.remote_addr) not in permission_ip_list:
                abort(jsonify({'code': 'fail', 'message': 'IP ' + request.remote_addr + ' not permitted', 'data': ''}))
            return f(*args, **kwargs)

        return decorated_function

    return decorator
