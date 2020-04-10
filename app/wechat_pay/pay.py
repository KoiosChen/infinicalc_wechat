#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import traceback
import logging
import uuid
import requests
import json
import xmltodict
import time
import pymysql
import datetime
import random

from hashlib import md5

MYSQL = dict(
    host='127.0.0.1', user='mysql_user', passwd='mysql_pwd', db='mydb', charset="utf8mb4"
)
logger = logging.getLogger(__name__)
conn = pymysql.connect(**MYSQL)
cur_dict = conn.cursor(pymysql.cursors.DictCursor)
cur = conn.cursor()


# 微信支付APP_ID
WEIXIN_APP_ID = 'wx91f04ffbf8a23431'
# 微信支付MCH_ID 【登录账号】
WEIXIN_MCH_ID = '1535411231'
# 微信支付sign_type
WEIXIN_SIGN_TYPE = 'MD5'
# 服务器IP地址
WEIXIN_SPBILL_CREATE_IP = '32.23.11.34'
# 微信支付用途
WEIXIN_BODY = '费用充值'
# 微信KEY值 【API密钥】
WEIXIN_KEY = 'ZiwcVpWomDqixQdhRgm5FpBKNXqwasde'
# 微信统一下单URL
WEIXIN_UNIFIED_ORDER_URL = 'https://api.mch.weixin.qq.com/pay/unifiedorder'
# 微信查询订单URL
WEIXIN_QUERY_ORDER_URL = 'https://api.mch.weixin.qq.com/pay/orderquery'
# 微信支付回调API
WEIXIN_CALLBACK_API = 'http://xxxx.com/weixinpay_rollback/'


def make_payment_info(notify_url=None, out_trade_no=None, total_fee=None):
    order_info = {'appid': WEIXIN_APP_ID,
                  'mch_id': WEIXIN_MCH_ID,
                  'device_info': 'WEB',
                  'nonce_str': '',
                  'sign_type': WEIXIN_SIGN_TYPE,
                  'body': WEIXIN_BODY,
                  'out_trade_no': str(out_trade_no),
                  'total_fee': total_fee,
                  'spbill_create_ip': WEIXIN_SPBILL_CREATE_IP,
                  'notify_url': notify_url,
                  'trade_type': 'APP'}
    return order_info


def make_payment_request_wx(notify_url, out_trade_no, total_fee):
    """
    微信统一下单，并返回客户端数据
    :param notify_url: 回调地址
    :param out_trade_no: 订单编号
    :param total_fee: 充值金额
    :return: app所需结果数据
    """

    def generate_call_app_data(params_dict, prepay_id):
        """
        客户端APP的数据参数包装
        """
        request_order_info = {'appid': params_dict['appid'],
                              'partnerid': params_dict['mch_id'],
                              'prepayid': prepay_id,
                              'package': 'Sign=WXPay',
                              'noncestr': generate_nonce_str(),
                              'timestamp': str(int(time.time()))}
        request_order_info['sign'] = generate_sign(request_order_info)
        return request_order_info

    def generate_sign(params):
        """
        生成md5签名的参数
        """
        if 'sign' in params:
            params.pop('sign')
        src = '&'.join(['%s=%s' % (k, v) for k, v in sorted(params.items())]) + '&key=%s' % WEIXIN_KEY
        return md5(src.encode('utf-8')).hexdigest().upper()

    def generate_nonce_str():
        """
        生成随机字符串
        """
        return str(uuid.uuid4()).replace('-', '')

    def generate_request_data(params_dict):
        """
        生成统一下单请求所需要提交的数据
        """
        params_dict['nonce_str'] = generate_nonce_str()
        params_dict['sign'] = generate_sign(params_dict)
        return xmltodict.unparse({'xml': params_dict}, pretty=True, full_document=False).encode('utf-8')

    def make_payment_request(params_dict, unified_order_url):
        """
        生成返回给客户端APP的数据参数
        """
        data = generate_request_data(params_dict)
        headers = {'Content-Type': 'application/xml'}
        res = requests.post(unified_order_url, data=data, headers=headers)
        if res.status_code == 200:
            result = json.loads(json.dumps(xmltodict.parse(res.content)))
            if result['xml']['return_code'] == 'SUCCESS':
                prepay_id = result['xml']['prepay_id']
                return generate_call_app_data(params_dict, prepay_id), result['xml']
            else:
                return result['xml']['return_msg'], None
        return None, None

    if float(total_fee) < 0.01:
        raise Exception('充值金额不能小于0.01')
    payment_info = make_payment_info(notify_url=notify_url, out_trade_no=out_trade_no, total_fee=total_fee)
    res, info = make_payment_request(payment_info, WEIXIN_UNIFIED_ORDER_URL)
    return res, info


def create_order(data, out_trade_no):
    """
    创建订单信息，存入库中
    :return:
    """
    insert_sql = ''' insert into {table}(status, app_id, seller_id, device_info, trade_type, prepay_id, trade_status, 
    out_trade_no, total_amount) 
     values (3, '{app_id}', '{seller_id}', '{device_info}', '{trade_type}', '{prepay_id}', '{trade_status}', 
     '{out_trade_no}', '{total_amount}')'''

    app_id = data['appid']  # 应用ID
    seller_id = data['mch_id']  # 商户号
    device_info = data['device_info']  # 微信支付分配的终端设备号
    trade_status = data['result_code']  # 业务结果 SUCCESS/FAIL
    total_amount = data['total_amount']  # 总金额
    if trade_status == "SUCCESS":
        trade_type = data['trade_type']  # 交易类型
        prepay_id = data['prepay_id']  # 预支付交易会话标识
        insert_sql = insert_sql.format(
            app_id=app_id,
            seller_id=seller_id,
            device_info=device_info,
            trade_type=trade_type,
            prepay_id=prepay_id,
            trade_status=trade_status,
            out_trade_no=out_trade_no,
            total_amount=total_amount / 100  # 将微信的分转为元
        )
        cur_dict.execute(insert_sql)
        return True
    else:
        return False


def create_order_number():
    """
    生成订单号
    :return:
    """
    date = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    # 生成4为随机数作为订单号的一部分
    random_str = str(random.randint(1, 9999))
    random_str = random_str.rjust(4, '0')
    rtn = '%s%s%s' % (date, random_str)
    return rtn


def weixin_create_order(request):
    """
    【API】: 创建订单,供商户app调用
    """
    res = {
        'code': 1,
        'msg': 'error'
    }
    try:
        price = 0.99  # 0.99元，微信的单位为分，需要转为分
        out_trade_no = create_order_number()
        order_info, info = make_payment_request_wx(WEIXIN_CALLBACK_API, out_trade_no, int(price * 100))
        if order_info and info:
            info['total_amount'] = int(price * 100)
            if info['result_code'] == "SUCCESS":
                order_info['out_trade_no'] = out_trade_no
                res['order_info'] = order_info
                create_order(info, out_trade_no)
            # 调用统一创建订单接口失败
            else:
                res['msg'] = info['result_code']
        elif order_info:
            res['msg'] = order_info
            res['code'] = -1
        else:
            res['code'] = -2
    except Exception:
        traceback.print_exc()
    finally:
        return json.dumps(res)
