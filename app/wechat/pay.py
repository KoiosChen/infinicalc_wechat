# -*- coding: utf-8 -*-
from app import logger, db, redis_db, sku_lock
from app.models import ShopOrders, Benefits, ShoppingCart, PackingItemOrders
from app.wechat.wechat_config import app_id, WEIXIN_MCH_ID, WEIXIN_SIGN_TYPE, WEIXIN_SPBILL_CREATE_IP, WEIXIN_BODY, \
    WEIXIN_KEY, \
    WEIXIN_UNIFIED_ORDER_URL, WEIXIN_QUERY_ORDER_URL, WEIXIN_CALLBACK_API
import traceback
import uuid
import requests
import json
import xmltodict
import time
import datetime
import random
from hashlib import md5
from app.public_method import new_data_obj
from app.common import submit_return, success_return, false_return, session_commit
from app.mall.sku import compute_quantity
import threading


def make_payment_info(notify_url=None, out_trade_no=None, total_fee=None, openid=None):
    order_info = {'appid': app_id,
                  'mch_id': WEIXIN_MCH_ID,
                  'device_info': 'WEB',
                  'nonce_str': '',
                  'sign_type': WEIXIN_SIGN_TYPE,
                  'body': WEIXIN_BODY,
                  'out_trade_no': str(out_trade_no),
                  'total_fee': total_fee,
                  'spbill_create_ip': WEIXIN_SPBILL_CREATE_IP,
                  'notify_url': notify_url,
                  'trade_type': 'JSAPI',
                  'openid': openid}
    return order_info


def make_payment_request_wx(notify_url, out_trade_no, total_fee, openid):
    """
    微信统一下单，并返回客户端数据
    :param notify_url: 回调地址
    :param out_trade_no: 订单编号
    :param total_fee: 充值金额
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
        req = requests.post(unified_order_url, data=data, headers=headers)
        if req.status_code == 200:
            result = json.loads(json.dumps(xmltodict.parse(req.content)))
            xml_content = result['xml']
            if xml_content['return_code'] == 'SUCCESS' and xml_content['result_code'] == 'SUCCESS':
                prepay_id = xml_content['prepay_id']
                # 将组合数据再次签名
                return generate_call_app_data(params_dict, prepay_id), result['xml']
            elif xml_content['return_code'] == 'SUCCESS':
                return result['xml']['return_msg'], None
            else:
                return result['xml']['err_code'] + ': ' + result['xml']['err_code_des'], None
        return None, None

    if float(total_fee) < 0.01:
        raise Exception('金额不能小于0.01')

    # 返回统一下单接口请求参数
    payment_info = make_payment_info(notify_url=notify_url,
                                     out_trade_no=out_trade_no,
                                     total_fee=total_fee,
                                     openid=openid)

    # 统一下单接口提交请求
    res, info = make_payment_request(payment_info, WEIXIN_UNIFIED_ORDER_URL)
    return res, info


def create_order(**kwargs):
    """
    用于生成订单，此时还未支付
    :param kwargs:
    :return:
    """

    def __do_create(create_info, op_key, lock):
        if lock.acquire():
            try:
                order_info = create_info.get('order_info')
                packing_order = create_info.pop('packing_order')
                packing_obj = None
                if packing_order:
                    packing_obj = PackingItemOrders.query.get(packing_order)

                new_order = new_data_obj("ShopOrders", **order_info)
                if not new_order:
                    raise Exception("订单创建失败，订单号创建失败")
                if not new_order['status']:
                    return success_return(data=new_order['obj'].id, message='订单已存在')

                if packing_obj:
                    # packing_obj.shop_order_id = new_order['obj'].id
                    packing_obj.packing_item_order = new_order['obj']

                for item in create_info.get('select_items'):
                    item_obj = ShoppingCart.query.get(item)
                    if not item_obj:
                        raise Exception(f"购物车中{item}不存在")
                    sku = item_obj.desire_skus
                    if not sku or not sku.status or sku.delete_at:
                        raise Exception(f"购物车对应商品不存在")

                    item_order = {"order_id": new_order['obj'].id, "item_id": sku.id,
                                  "item_quantity": item_obj.quantity, "item_price": sku.price,
                                  "transaction_price": sku.price}
                    new_item_order = new_data_obj("ItemsOrders", **item_order)

                    if new_item_order and new_item_order.get('status'):
                        # 此处调用修改sku数量方法，数量传递为负数，因为这里一定是减少
                        change_result = compute_quantity(sku, -item_obj.quantity)

                        # 如果change_result是false， 那么表明出货失败
                        if change_result.get("code") == "false":
                            raise Exception(json.dumps(change_result))

                        # 如果这个sku有相关的促销活动，则记录
                        if item_obj.combo:
                            new_item_order['obj'].benefits.append(Benefits.query.get(item_obj.combo))

                    else:
                        raise Exception("订单创建失败")
                if session_commit().get("code") == 'false':
                    raise Exception("订单创建失败，因为事务提交失败")
            except Exception as e:
                redis_db.set(f"create_order::{create_info['order_info']['customer_id']}::{op_key}",
                             json.dumps(false_return(message=str(e))),
                             ex=6000)
            finally:
                lock.release()

    operate_key = str(uuid.uuid4())
    create_thread = threading.Thread(target=__do_create, args=(kwargs, operate_key, sku_lock))
    create_thread.start()
    create_thread.join()
    k = f"create_order::{kwargs['order_info']['customer_id']}::{operate_key}"
    if redis_db.exists(k):
        result = json.loads(redis_db.get(k))
        redis_db.delete(k)
        return result
    else:
        for i in kwargs['select_items']:
            cart = ShoppingCart.query.get(i)
            cart.delete_at = datetime.datetime.now()
            db.session.add(cart)
        db.session.commit()
        return success_return(message=f"创建订单成功")


def weixin_pay(out_trade_no, price, openid):
    """
    【API】: 创建订单,供商户app调用
    """
    order = ShopOrders.query.get(out_trade_no)
    try:
        # 后台提交支付请求
        if not order:
            raise Exception(f"订单 {out_trade_no} 不存在")
        if order.is_pay == 1 and order.pay_time:
            raise Exception(f"订单 {out_trade_no} 已支付")
        if order.is_pay == 3 and not order.pay_time:
            raise Exception(f"订单 {out_trade_no} 支付中")
        order_info, info = make_payment_request_wx(WEIXIN_CALLBACK_API,
                                                   out_trade_no,
                                                   int(price * 100),
                                                   openid)
        if order_info and info:
            info['total_amount'] = int(price * 100)
            if info['result_code'] == "SUCCESS":
                # 在返回小程序的package中增加订单号
                order_info['out_trade_no'] = out_trade_no
                order.is_pay = 3
                order.pre_pay_time = datetime.datetime.now()
                db.session.add(order)
                session_commit()
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
        order.is_pay = 2
        db.session.add(order)
        session_commit()
        return false_return(message=f"支付失败，{e}")
