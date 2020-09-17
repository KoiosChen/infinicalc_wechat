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
from app.public_method import session_commit, new_data_obj
import datetime
from app.rebates import calc_rebate



@wechat.route('/wechat_pay/callback/', methods=['POST','GET'])
def wechat_pay_callback():
    if request.method == 'GET':
        return 'GOT'
    else:
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
        src = '&'.join(['%s=%s' % (k, v) for k, v in sorted(params.items(), key=lambda d:d[0]) if k != "#text"]) + '&key=%s' % WEIXIN_KEY
        print(src)
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

    def handle_wx_response_xml():
        """
        处理微信支付返回的xml格式数据
        """
        resp_dict = xmltodict.parse(args)['xml']
        return_code = resp_dict.get('return_code')
        if return_code == 'SUCCESS':  # 仅仅判断通信标识成功，非交易标识成功，交易需判断result_code
            if validate_sign(resp_dict):
                return resp_dict
        else:
            print('FAIL')
        return

    args = request.data
    # 验证平台签名
    resp_dict = handle_wx_response_xml()
    # resp_dict = request.json
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

    return_code = 'SUCCESS' if params == 'success' else 'FAIL'
    return_msg = 'OK' if params == 'success' else params
    return_info = {
        'return_code': return_code,
        'return_msg': return_msg
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
            order = db.session.query(ShopOrders).with_for_update().filter(ShopOrders.id.__eq__(out_trade_no),
                                                                          ShopOrders.is_pay.__eq__(3),
                                                                          ShopOrders.status.__eq__(1),
                                                                          ShopOrders.delete_at.__eq__(None)).first()
            if not order:
                raise Exception(f"订单 {out_trade_no} 不存在，或已完成支付")

            if trade_status == "SUCCESS":
                bank_type = data['bank_type']  # 付款银行
                cash_fee = int(data['cash_fee']) / 100  # 现金支付金额(分)
                pay_time = datetime.datetime.strptime(data['time_end'], "%Y%m%d%H%M%S")  # 支付完成时间
                total_amount = int(data['total_fee']) / 100  # 总金额(单位由分转元)
                # trade_type = data['trade_type']  # 交易类型
                transaction_id = data['transaction_id']  # 微信支付订单号
                # seller_id = data['mch_id']  # 商户号
                consumer_openid = data['openid']  # 用户标识
                if consumer_openid != order.consumer.openid:
                    raise Exception(f"回调中openid {consumer_openid}与订单记录不符{order.consumer.openid}")

                items = order.items_orders_id.all()
                if items:
                    # 更新订单数据
                    order.is_pay = 1
                    order.bank_type = bank_type
                    order.cash_fee = cash_fee
                    order.pay_time = pay_time
                    order.transaction_id = transaction_id

                    # 封坛记录，生成封坛订单
                    for item_order in items:
                        item_order.status = 1
                        if item_order.special == 31:
                            # 封坛货物
                            standard_value = item_order.bought_sku.values
                            # 查找单位是‘斤’的数值
                            unit = ""
                            init_total = 0.00
                            for s in standard_value:
                                if s.standards.name == '斤':
                                    init_total = s.value
                                    unit = s.standards.name
                                    break

                            for _ in range(0, item_order.item_quantity):
                                cargo_data = {"cargo_code": make_order_id('FT'), 'order_id': order.id,
                                              "storage_date": datetime.datetime.now(),
                                              "init_total": init_total,
                                              "last_total": init_total,
                                              "unit": unit,
                                              "owner_name": order.consumer.true_name,
                                              "owner_id": order.customer_id}
                                new_cargo = new_data_obj("TotalCargoes", **cargo_data)
                                if not new_cargo and not new_cargo.get('status'):
                                    logger.error(f"{item_order.id}生成仓储记录失败，或者记录已存在")
                                    res = f"{item_order.id}生成仓储记录失败，或者记录已存在"
                        elif item_order.special == 32:
                            # 表示分装订单，此item为酒瓶
                            packing_order = order.packing_order.first()
                            packing_order.pay_at = pay_time
                            packing_order.parent_cargo.last_total -= packing_order.consumption

                    if res == 'success':
                        if session_commit().get("code") == 'success':
                            res = 'success'
                        else:
                            res = '数据提交失败'

                    # 返佣计算
                    calc_result = calc_rebate.calc(order.id, order.consumer)
                    if calc_result.get('code') != 'success':
                        res = calc_result.get('message')

                    if res == 'success':
                        if session_commit().get("code") == 'success':
                            res = 'success'
                        else:
                            res = '数据提交失败'
                else:
                    res = '此订单无关联商品订单'
            else:
                res = "error: pay failed! "
                # 更新订单，把错误信息更新到订单中
                order.is_pay = 2
                order.pay_err_code = data['err_code']  # 错误代码
                order.pay_err_code_des = data['err_code_des']  # 错误代码描述
                db.session.add(order)
                session_commit()
        else:
            res = "回调无内容"
    except Exception as e:
        traceback.print_exc()
        res = str(e)
    finally:
        logger.debug(res)
        return weixinpay_response_xml(res)
