# -*- coding: utf-8 -*-
from app import db, redis_db, sku_lock
from app.models import ShopOrders, Benefits, ShoppingCart, PackingItemOrders, Customers, MemberRechargeRecords, \
    make_uuid, CERT_PATH, KEY_PATH
from app.wechat.wechat_config import WEIXIN_PURSE_API
import traceback
import requests
import json
import time
import datetime
from app.public_method import new_data_obj, calc_sku_price
from app.common import success_return, false_return, session_commit
from app.mall.sku import compute_quantity
import threading
from .public_method import *


def make_payment_info(partner_trade_no=None, amount=None, openid=None, device_info=None, check_name='NO_CHECK', spbill_create_ip=None, desc='返佣提现'):
    order_info = {'mch_appid': app_id,
                  'mchid': WEIXIN_MCH_ID,
                  'device_info': device_info,
                  'nonce_str': '',
                  'partner_trade_no': str(partner_trade_no),
                  'openid': openid,
                  'check_name': check_name,
                  'amount': amount,
                  'desc': desc,
                  'spbill_create_ip': spbill_create_ip}
    return order_info


def request_wx_pay(partner_trade_no, amount, openid):
    """
    微信统一下单，并返回客户端数据
    :param out_trade_no: 订单编号
    :param total_fee: 提现金额
    :param openid: openid
    :return: app所需结果数据
    """

    def generate_call_app_data(params_dict, prepay_id):
        """
        将组合数据再次签名，客户端APP的数据参数包装
        """
        request_order_info = {
            'appId': params_dict['appid'],
            'nonceStr': generate_nonce_str(),
            'package': "prepay_id=" + prepay_id,
            'signType': 'MD5',
            'timeStamp': str(int(time.time()))
        }
        request_order_info['sign'] = generate_sign(request_order_info)
        return request_order_info

    def make_payment_request(params_dict, unified_order_url):
        """
        生成返回给客户端APP的数据参数
        """
        data = generate_request_data(params_dict)
        headers = {'Content-Type': 'application/xml'}
        req = requests.post(unified_order_url, data=data, headers=headers, cert=(CERT_PATH, KEY_PATH))
        if req.status_code == 200:
            result = json.loads(json.dumps(xmltodict.parse(req.content)))
            logger.debug(result)
            xml_content = result['xml']
            if xml_content['return_code'] == 'SUCCESS' and xml_content['result_code'] == 'SUCCESS':
                prepay_id = xml_content['prepay_id']
                # 将组合数据再次签名
                return generate_call_app_data(params_dict, prepay_id), result['xml']
            elif xml_content['return_code'] == 'SUCCESS':
                return result['xml']['err_code'] + ": " + result['xml']['err_code_des'], None
            else:
                return result['xml']['return_code'] + ': ' + result['xml']['return_msg'], None
        return None, None

    if float(amount) < 0.01:
        raise Exception('金额不能小于0.01')

    # 返回统一下单接口请求参数
    payment_info = make_payment_info(partner_trade_no=partner_trade_no, amount=amount, openid=openid)

    # 统一下单接口提交请求
    res, info = make_payment_request(payment_info, WEIXIN_PURSE_API)
    return res, info


def weixin_pay_purse(order_id, amount, customer_id, check_name="NO_CHECK"):
    """
    【API】: 创建订单,供商户app调用
    """
    try:
        customer = db.session.query(Customers).with_for_update().filter(Customers.id.__eq__(customer_id)).first()
        if amount > customer.purse:
            raise Exception("取现金额大于账户余额")

        new_weixin_pay_purse_order = new_data_obj("WechatPurseTransfer",
                                                  **{"id": order_id,
                                                     "customer_id": customer_id,
                                                     "amount": amount})
        if not new_weixin_pay_purse_order:
            raise Exception("创建取现订单失败")

        try:
            # 提交支付到零钱
            order_info, info = request_wx_pay(order_id, int(amount * 100), customer.openid)

            if order_info and info:
                info['total_amount'] = int(price * 100)
                if info['result_code'] == "SUCCESS":
                    # 在返回小程序的package中增加订单号
                    order_info['out_trade_no'] = out_trade_no
                    order.is_pay = 3
                    order.pre_pay_time = datetime.datetime.now()
                    if info['device_info'] == "MemberRecharge":
                        # 如果是购物车中直接消费，那么正常情况没有微信支付记录
                        # 如果是订单中再付费，那么正常情况应该已经有微信支付记录
                        if not order.wechat_pay_result:
                            # 创建微信支付记录
                            new_wechat_pay = new_data_obj("WechatPay", **{"id": make_uuid(),
                                                                          "openid": customer.openid,
                                                                          "member_recharge_record_id": out_trade_no})
                            if not new_wechat_pay or not new_wechat_pay['status']:
                                raise Exception("创建支付关联记录失败")

                            new_wechat_pay['obj'].prepay_id = info['prepay_id']
                            new_wechat_pay['obj'].prepay_at = datetime.datetime.now()
                            new_wechat_pay['obj'].device_info = info['device_info']

                    db.session.add(order)
                    if session_commit().get('code') == 'false':
                        raise Exception("订单数据提交失败，事务回滚")
                    return success_return(data=order_info, message="订单预付id获取成功")
                # 调用统一创建订单接口失败
                else:
                    raise Exception(info['result_code'])
            elif order_info:
                raise Exception(order_info)
            else:
                raise Exception("请求无响应")
        except Exception as e:
            traceback.print_exc()
            if order and order.is_pay != 1:
                order.is_pay = 2
                db.session.add(order)
            session_commit()
            return false_return(message=f"支付失败，{e}")
    except Exception as e:
        return false_return(message=str(e)), 400
