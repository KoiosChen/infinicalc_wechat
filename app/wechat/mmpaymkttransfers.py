# -*- coding: utf-8 -*-
from app import db
from app.models import WechatPurseTransfer, CERT_PATH, KEY_PATH, RETRY_ERR_CODE
import traceback
import requests
import json
from app.common import success_return, false_return, session_commit
from .public_method import *
import datetime


def make_payment_info(partner_trade_no=None, openid=None, check_name='NO_CHECK', re_user_name=None, amount=None,
                      desc=None, spbill_create_ip=None):
    order_info = {'mch_appid': app_id,
                  'mch_id': WEIXIN_MCH_ID,
                  'nonce_str': '',
                  'partner_trade_no': str(partner_trade_no),
                  'openid': str(openid),
                  'check_name': str(check_name),
                  're_user_name': re_user_name if re_user_name is not None else "",
                  'amount': amount,
                  'desc': str(desc),
                  'spbill_create_ip': str(spbill_create_ip)}
    return order_info


def make_transfer_request_wx(partner_trade_no=None, openid=None, check_name='NO_CHECK', re_user_name=None, amount=None,
                             desc=None, spbill_create_ip=None):
    """

    :param partner_trade_no:
    :param openid:
    :param check_name:
    :param re_user_name:
    :param amount:
    :param desc:
    :param spbill_create_ip:
    :return:
    """

    def make_payment_request(params_dict, unified_order_url):
        """
        生成返回给客户端APP的数据参数
        """
        data = generate_request_data(params_dict)
        headers = {'Content-Type': 'application/xml'}
        logger.debug(CERT_PATH + " " + KEY_PATH)
        req = requests.post(unified_order_url, data=data, headers=headers, cert=(CERT_PATH, KEY_PATH))
        if req.status_code == 200:
            result = json.loads(json.dumps(xmltodict.parse(req.content)))
            logger.debug(result)
            xml_content = result['xml']
            if xml_content['return_code'] == 'SUCCESS' and xml_content['result_code'] == 'SUCCESS':
                return success_return(data=result['xml'])
            elif xml_content['return_code'] == 'SUCCESS':
                return {"return_code": 'SUCCESS',
                        "result_code": "FAIL",
                        "err_code": xml_content['err_code'],
                        "err_code_desc": xml_content['err_code_des']}
            else:
                return {"return_code": xml_content['return_code'],
                        "return_msg": xml_content['return_msg']}
        return None

    if float(amount) < 0.01:
        raise Exception('金额不能小于0.01')

    # 返回退货接口请求参数
    payment_info = make_payment_info(partner_trade_no=partner_trade_no,
                                     openid=openid,
                                     check_name=check_name,
                                     re_user_name=re_user_name,
                                     amount=amount,
                                     desc=desc,
                                     spbill_create_ip=spbill_create_ip)

    # 退货接口提交请求
    res = make_payment_request(payment_info, WEIXIN_REFUND_API)
    return res


def weixin_purse_transfer(partner_trade_no, openid, spbill_create_ip):
    """
    【API】: 企业微信转零钱,返佣用
    """
    transfer_order = db.session.query(WechatPurseTransfer).with_for_update().filter(
        WechatPurseTransfer.id.__eq__(partner_trade_no),
        WechatPurseTransfer.result_code.__ne__("SUCCESS"),
        WechatPurseTransfer.delete_at.__eq__(None)).first()

    try:
        # 后台提交退货请求
        if not transfer_order:
            raise Exception(f"转零钱订单 {partner_trade_no} 不存在或者已支付完成")
        elif transfer_order.err_code and transfer_order.err_code not in RETRY_ERR_CODE:
            raise Exception(f"当前错误不可重复尝试")

        # 提交支付
        order_info = make_transfer_request_wx(partner_trade_no=partner_trade_no, openid=openid,
                                              amount=transfer_order.amount, desc=transfer_order.desc,
                                              spbill_create_ip=spbill_create_ip)

        if order_info['return_code'] == "SUCCESS" and order_info['result_code'] == "SUCCESS":
            logger.info(f"转零钱订单{partner_trade_no}提交成功")
            transfer_order.result_code = order_info['result_code']
            transfer_order.payment_no = order_info['payment_no']
            transfer_order.payment_time = datetime.datetime.strptime(order_info['pay_time'], "%Y-%m-%d %H:%M:%S")
            db.session.add(transfer_order)
            if session_commit().get('code') == 'false':
                raise Exception("订单数据提交失败，事务回滚")
            return success_return(data=order_info, message=f"转零钱订单<{partner_trade_no}>支付成功")
        elif order_info['return_code'] == "SUCCESS":
            transfer_order.result_code = order_info['result_code']
            transfer_order.err_code = order_info['err_code']
            transfer_order.err_code_des = order_info['err_code_des']
            db.session.add(transfer_order)
            if session_commit().get('code') == 'false':
                raise Exception(f"{order_info}订单数据提交失败，事务回滚")
            raise Exception(order_info)
        else:
            raise Exception("请求无响应")
    except Exception as e:
        traceback.print_exc()
        return false_return(message=f"支付失败，{e}")
