import jwt
import datetime
import time
from ..models import Elements, LoginInfo, Customers
from .. import db, logger, SECRET_KEY
from ..common import success_return, false_return, session_commit
from ..public_method import new_data_obj
from sqlalchemy import or_, and_
from ..public_method import table_fields, get_table_data_by_id
import json
import traceback


def encode_auth_token(user_id, login_time, login_ip, platform):
    """
    生成认证Token
    “exp”: 过期时间
    “nbf”: 表示当前时间在nbf里的时间之前，则Token不被接受
    “iss”: token签发者
    “aud”: 接收者
    “iat”: 发行时间
    :param user_id: string
    :param login_time: int(timestamp)
    :param login_ip: string
    :return: string
    """
    try:
        payload = {
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=0, seconds=86400),
            'iat': datetime.datetime.utcnow(),
            'iss': 'infinicalc.com',
            'data': {
                'id': user_id,
                'login_time': login_time,
                'login_ip': login_ip,
                'platform': platform
            }
        }
        return jwt.encode(
            payload,
            SECRET_KEY,
            algorithm='HS256'
        )
    except Exception as e:
        logger.error(str(e))
        return false_return(message=str(e))


def authenticate(login_ip, **kwargs):
    """
    前端用户登录，目前只针对微信小程序环境
    :param kwargs: code2session接口返回的json
    :param login_ip: 用户发起请求的IP
    :return: json
    """
    try:
        open_id = kwargs['openid']
        session_key = kwargs['session_key']
        new_customer = new_data_obj("Customers", **{"openid": open_id, "delete_at": None, "status": 1})
        customer = new_customer['obj']

        # 如果父级id为空，那么将此次父级id作为自己的父级
        if kwargs.get('shared_id'):
            # 查找分享者是否存在
            shared_customer_ = Customers.query.filter(Customers.openid.__eq__(kwargs['shared_id']),
                                                      Customers.delete_at.__eq__(None)).first()
            if not shared_customer_:
                logger.error(f"{kwargs.get('shared_id')} is not exist!")
            else:
                # shared_customer = Customers.query.get(customer) if isinstance(customer, str) else customer
                shared_member_card = shared_customer_.member_card.filter_by(status=1, member_type=1).first()
                if not customer.parent_id:
                    # 写入分享关系，不可修改
                    customer.parent_id = shared_customer_.id

                if not customer.interest_id:
                    if shared_member_card:
                        # 上级如果是代理商，interest_id，利益关系挂在上级ID
                        customer.interest_id = shared_customer_.id
                    else:
                        # 如果分享来自直客，interest_id，如果直客没有interest_id,则都没有利益关系
                        customer.interest_id = shared_customer_.interest_id

        # 查询并删除已经登陆的信息
        logged_in_info = customer.login_info.filter_by(platform="wechat", status=True).all()
        for lg in logged_in_info:
            db.session.delete(lg)
        db.session.flush()

        login_time = int(time.time())

        new_data_obj("LoginInfo",
                     **{
                         'token': session_key,
                         'login_time': login_time,
                         'login_ip': login_ip,
                         'customer': customer.id,
                         'platform': 'wechat',
                         'status': True
                     }
                     )
        db.session.add(customer)
        commit_result = session_commit()
        if commit_result.get("code") == "false":
            raise Exception(json.dumps(commit_result))

        ru = get_table_data_by_id(Customers, customer.id, ["role", "member_info"], ["role_id"])

        return success_return(data={'customer_info': ru, 'session_key': session_key}, message='登录成功')
    except Exception as e:
        traceback.print_exc()
        return false_return(data=str(e), message='登陆失败'), 400


def decode_auth_token(auth_token):
    """
    验证Token
    :param auth_token:
    :return: integer|string
    """
    try:
        payload = jwt.decode(auth_token, SECRET_KEY, leeway=datetime.timedelta(seconds=10))
        # 取消过期时间验证
        # payload = jwt.decode(auth_token, config.SECRET_KEY, options={'verify_exp': False})
        if 'data' in payload.keys() and 'id' in payload['data'].keys():
            return success_return(data=payload)
        else:
            raise jwt.InvalidTokenError
    except jwt.ExpiredSignatureError:
        return false_return(message='Token过期')
    except jwt.InvalidTokenError:
        return false_return(message='无效Token')


def identify(request):
    """
    用户鉴权
    :param: request
    :return: json
    """
    auth_header = request.headers.get('Authorization')
    if auth_header:
        auth_token_arr = auth_header.split(" ")
        if not auth_token_arr or auth_token_arr[0] != 'Bearer' or len(auth_token_arr) != 2:
            result = false_return(message='请传递正确的验证头信息')
        else:
            auth_token = auth_token_arr[1]
            if not LoginInfo.query.filter_by(token=auth_token).first():
                return false_return(message='认证失败')
            payload = decode_auth_token(auth_token)
            if payload['code'] == 'success':
                data = payload['data']['data']
                user = Customers.query.filter_by(id=data['id']).first()
                if user is None:
                    result = false_return('', '找不到该用户信息')
                else:
                    login_info = LoginInfo.query.filter_by(token=auth_token, customer=user.id).first()
                    if login_info and login_info.login_time == data['login_time']:
                        result = success_return(data={"user": user, "login_info": login_info}, message='请求成功')
                    else:
                        result = false_return(message='Token已更改，请重新登录获取')
            else:
                result = false_return(message=payload['message'])
    else:
        result = false_return(message='没有提供认证token')
    return result
