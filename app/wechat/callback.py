#!/usr/bin/env python
# -*- coding: utf-8 -*-
from app import logger, redis_db, db
from app.models import ShopOrders, make_order_id
from . import wechat
from app.wechat.wechat_config import WEIXIN_APP_ID, WEIXIN_MCH_ID, WEIXIN_SIGN_TYPE, WEIXIN_SPBILL_CREATE_IP, \
    WEIXIN_BODY, \
    WEIXIN_KEY, WEIXIN_UNIFIED_ORDER_URL, WEIXIN_QUERY_ORDER_URL, WEIXIN_CALLBACK_API
import traceback
import logging
import xmltodict
import pymysql
from flask import request, jsonify
from hashlib import md5
from app.common import submit_return, false_return, success_return
from app.public_method import session_commit
import datetime


@wechat.route('/wechat_pay/callback', methods=['POST'])
def wechat_pay_callback():
    return weixin_rollback(request)


def weixinpay_call_back(request):
    """
    微信支付回调
    :param args: 回调参数
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

    args = request.data
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


def create_cargoes(**kwargs):
    """
    如果是需要仓储，有分装（分发）流程的货物，则产生仓储记录
    :param kwargs:
    :return:
    """


def weixin_rollback(request):
    """
    【API】: 微信支付结果回调接口,供微信服务端调用
    """
    try:
        # 支付异步回调验证
        data = weixinpay_call_back(request)
        if data:
            res = "success"

            trade_status = data['result_code']  # 业务结果  SUCCESS/FAIL
            out_trade_no = data['out_trade_no']  # 商户订单号
            order = ShopOrders.query.get(out_trade_no)
            if not order:
                raise Exception(f"订单 {out_trade_no} 不存在")

            if trade_status == "SUCCESS":
                status = 1
                bank_type = data['bank_type']  # 付款银行
                cash_fee = data['cash_fee']  # 现金支付金额(分)
                pay_time = data['time_end']  # 支付完成时间
                total_amount = int(data['total_fee']) / 100  # 总金额(单位由分转元)
                trade_type = data['trade_type']  # 交易类型
                transaction_id = data['transaction_id']  # 微信支付订单号
                seller_id = data['mch_id']  # 商户号
                buyer_id = data['openid']  # 用户标识
                if buyer_id != order.buyer.id:
                    raise Exception(f"回调中openid {buyer_id}与订单记录不符{order.buyer.id}")

                # 更新订单数据
                order.is_pay = 1
                order.bank_type = bank_type
                order.cash_free = cash_fee
                order.pay_time = pay_time
                order.transaction_id = transaction_id
                items = order.items_orders_id.all()
                if items:
                    for item_order in items:
                        if item_order.special >= 30:
                            cargo_data = {"cargo_code": make_order_id('FT'), 'order_id': order.id,
                                          "storage_date":datetime.datetime.now(),
                                          "init_total": item_order.item_id.first().values.get(0).value,
                                          "unit": item_order.item_id.first().values.get(0).standards.name}

                else:
                    res = "error: pay failed! "
                    status = 0
                    err_code = data['err_code']  # 错误代码
                    err_code_des = data['err_code_des']  # 错误代码描述
                    # 更新订单，把错误信息更新到订单中
                    order.is_pay = 2
                    order.pay_err_code = err_code
                    order.pay_err_code_des = err_code_des
                db.session.add(order)
                if session_commit().get("code") == 'success':
                    res = 'success'
            else:
                res = "回调无内容"
        except Exception as e:
        traceback.print_exc()
        res = str(e)
    finally:
        return weixinpay_response_xml(res)
