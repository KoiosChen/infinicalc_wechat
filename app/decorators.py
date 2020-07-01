from functools import wraps
from flask import abort, request, make_response
from . import logger
from .common import false_return, exp_return
from app.auth.auths import identify
from app.frontstage_auth import auths
from flask import make_response


def allow_cross_domain(fun):
    @wraps(fun)
    def wrapper_fun(*args, **kwargs):
        rst = make_response(fun(*args, **kwargs))
        rst.headers['Access-Control-Allow-Origin'] = '*'
        rst.headers['Access-Control-Allow-Methods'] = 'PUT,GET,POST,DELETE'
        allow_headers = "Referer,Accept,Origin,User-Agent"
        rst.headers['Access-Control-Allow-Headers'] = allow_headers
        return rst

    return wrapper_fun


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        logger.info(
            'IP {} is checking login status'.format(
                request.headers.get('X-Forwarded-For', request.remote_addr)))
        if not identify(request).get('code') == "success":
            abort(make_response(false_return(message='用户未登陆'), 401))
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
                if permission not in [p.permission for p in current_user['data']['user'].permissions]:
                    logger.warn('This user\'s action is not permitted!')
                    abort(make_response(false_return(message='This user\'s action is not permitted!'), 403))
            elif current_user.get("code") == "success" and "admin" in [r.name for r in
                                                                       current_user['data']['user'].roles]:
                pass

            else:
                abort(make_response(exp_return(message=current_user.get("message")), 403))
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
                abort(make_response(false_return(message='IP ' + request.remote_addr + ' not permitted')), 403)
            return f(*args, **kwargs)

        return decorated_function

    return decorator
