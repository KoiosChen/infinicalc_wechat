from functools import wraps
from flask import abort, request, make_response
from . import logger
from .common import false_return, exp_return
from app.auth.auths import identify
from app.frontstage_auth import auths
from flask import make_response
from app.models import Customers


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

            def __check(permit):
                # 区分前后台，前端传递的permission为int类型，并且header中的Authorization 不包括Bearer关键字
                # 后端传递的permission为str类型，并且必须在header中的Authorization包括Bearer
                if isinstance(permit, int) and 'Bearer' not in request.headers.get('Authorization'):
                    open_id = request.headers.get('Authorization')
                    customer = Customers.query.filter_by(openid=open_id, status=1, delete_at=None).first()
                    if not customer or not customer.can(permit):
                        logger.warn('This user\'s action is not permitted!')
                        # abort(make_response(false_return(message='This user\'s action is not permitted!'), 403))
                    kwargs['current_user'] = customer
                elif isinstance(permit, str) and 'Bearer' in request.headers.get('Authorization'):
                    current_user = identify(request)

                    if current_user.get('code') == 'success' and 'logout' in permit:
                        kwargs['info'] = current_user['data']
                        return f(*args, **kwargs)

                    if current_user.get("code") == "success" and "admin" not in [r.name for r in
                                                                                 current_user['data']['user'].roles]:
                        if permit not in [p.permission for p in current_user['data']['user'].permissions]:
                            logger.warn('This user\'s action is not permitted!')
                            # abort(make_response(false_return(message='This user\'s action is not permitted!'), 403))
                    elif current_user.get("code") == "success" and "admin" in [r.name for r in
                                                                               current_user['data']['user'].roles]:
                        pass

                    else:
                        # abort(make_response(exp_return(message=current_user.get("message")), 403))
                        pass
                    kwargs['info'] = current_user['data']
                else:
                    # abort(make_response(exp_return(message=current_user.get("message")), 403))
                    pass

            if isinstance(permission, list):
                # 当permission为list时，表示这个接口是公共接口
                for p in permission:
                    __check(p)
            else:
                __check(permission)
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
