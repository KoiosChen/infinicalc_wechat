#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import traceback
import logging
import xmltodict
import pymysql

from hashlib import md5

MYSQL = dict(
    host='127.0.0.1', user='mysql_user', passwd='mysql_pwd', db='mydb', charset="utf8mb4"
)
logger = logging.getLogger(__name__)
conn = pymysql.connect(**MYSQL)
cur_dict = conn.cursor(pymysql.cursors.DictCursor)
cur = conn.cursor()

###############################################
#############    微信支付配置   #################
###############################################
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


def weixinpay_call_back(request):
    """
    微信支付回调
    :param request: 回调参数
    :return:
    """

    def generate_sign(params):
        """
        生成md5签名的参数
        """
        if 'sign' in params:
            params.pop('sign')
        src = '&'.join(['%s=%s' % (k, v) for k, v in sorted(params.items())]) + '&key=%s' % WEIXIN_KEY
        return md5(src.encode('utf-8')).hexdigest().upper()

    def validate_sign(resp_dict):
        """
        验证微信返回的签名
        """
        if 'sign' not in resp_dict:
            return False
        wx_sign = resp_dict['sign']
        sign = generate_sign(resp_dict)
        if sign == wx_sign:
            return True
        return False

    def handle_wx_response_xml(params):
        """
        处理微信支付返回的xml格式数据
        """
        resp_dict = xmltodict.parse(params)['xml']
        return_code = resp_dict.get('return_code')
        if return_code == 'SUCCESS':  # 仅仅判断通信标识成功，非交易标识成功，交易需判断result_code
            if validate_sign(resp_dict):
                return resp_dict
        else:
            print('FAIL')
        return

    args = request.body
    # 验证平台签名
    resp_dict = handle_wx_response_xml(args)
    if resp_dict is None:
        return None
    return resp_dict


def weixinpay_response_xml(params):
    """
    生成交易成功返回信息
    """

    def generate_response_data(resp_dict):
        """
        字典转xml
        """
        return xmltodict.unparse({'xml': resp_dict}, pretty=True, full_document=False).encode('utf-8')

    return_info = {
        'return_code': params,
        'return_msg': 'OK'
    }
    return generate_response_data(return_info)


def weixin_rollback(request):
    """
    【API】: 微信宝支付结果回调接口,供微信服务端调用
    """
    try:
        # 支付异步回调验证
        data = weixinpay_call_back(request)
        if data:
            res = "success"

            trade_status = data['result_code']  # 业务结果  SUCCESS/FAIL
            out_trade_no = data['out_trade_no']  # 商户订单号
            if trade_status == "SUCCESS":
                status = 1
                app_id = data['appid']  # 应用ID
                bank_type = data['bank_type']  # 付款银行
                cash_fee = data['cash_fee']  # 现金支付金额(分)
                device_info = data['device_info']  # 微信支付分配的终端设备号
                fee_type = data['fee_type']  # 货币种类
                gmt_create = data['time_end']  # 支付完成时间
                total_amount = int(data['total_fee']) / 100  # 总金额(单位由分转元)
                trade_type = data['trade_type']  # 交易类型
                trade_no = data['transaction_id']  # 微信支付订单号
                seller_id = data['mch_id']  # 商户号
                buyer_id = data['openid']  # 用户标识

                update_sql = ''' update orders set trade_status='{trade_status}', app_id='{app_id}', 
                                    seller_id='{seller_id}', buyer_id='{buyer_id}', total_amount='{total_amount}', 
                                    out_trade_no='{out_trade_no}', gmt_create='{gmt_create}', trade_no='{trade_no}', 
                                    device_info='{device_info}', trade_type='{trade_type}', bank_type='{bank_type}', 
                                    fee_type='{fee_type}', cash_fee='{cash_fee}',  
                                    status='{status}' where out_trade_no='{out_trade_no}' '''
                update_sql = update_sql.format(
                    app_id=app_id,
                    bank_type=bank_type,
                    cash_fee=cash_fee,
                    device_info=device_info,
                    fee_type=fee_type,
                    out_trade_no=out_trade_no,
                    gmt_create=gmt_create,
                    total_amount=total_amount,
                    trade_type=trade_type,
                    trade_no=trade_no,
                    seller_id=seller_id,
                    buyer_id=buyer_id,
                    trade_status=trade_status,
                    status=status
                )
            else:
                res = "error: pay failed! "
                status = 0
                err_code = data['err_code']  # 错误代码
                err_code_des = data['err_code_des']  # 错误代码描述
                update_sql = ''' update orders set trade_status='{trade_status}', err_code='{err_code}', 
                err_code_des='{err_code_des}', status='{status}' where out_trade_no='{out_trade_no}'  '''
                update_sql = update_sql.format(
                    out_trade_no=out_trade_no,
                    trade_status=trade_status,
                    status=status,
                    err_code=err_code,
                    err_code_des=err_code_des,
                )

            cur_dict.execute(update_sql)
            conn.commit()
        else:
            res = "error: verify failed! "
    except Exception:
        traceback.print_exc()
    finally:
        return weixinpay_response_xml(res)
