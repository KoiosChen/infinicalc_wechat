# -*- coding: utf-8 -*-
from app.wechat.wechat_config import WEIXIN_APP_ID, WEIXIN_MCH_ID, WEIXIN_SIGN_TYPE, WEIXIN_SPBILL_CREATE_IP, WEIXIN_BODY, \
    WEIXIN_KEY, WEIXIN_UNIFIED_ORDER_URL, WEIXIN_QUERY_ORDER_URL, WEIXIN_CALLBACK_API
import traceback
import xmltodict
import uuid
import json
import requests
from hashlib import md5


def update_order(data):
    """
    查询支付订单，并更新订单
    :param data:
    :return:
    """
    # err_code = data['err_code']  # 错误代码
    # err_code_des = data['err_code_des']  # 错误代码描述
    trade_status = data['result_code']  # 业务结果 SUCCESS/FAIL
    app_id = data['appid']  # 应用ID
    seller_id = data['mch_id']  # 商户号
    if trade_status == "SUCCESS":
        buyer_id = data['openid']  # 用户标识
        total_amount = int(data['total_fee']) / 100  # 总金额(元)
        out_trade_no = data['out_trade_no']  # 商户订单号
        gmt_create = data['time_end']  # 支付完成时间
        trade_no = data['transaction_id']  # 微信支付订单号
        trade_status = data['trade_state']  # 交易状态
        if trade_status == "SUCCESS":
            status = 1
        elif trade_status == "USERPAYING":
            status = 2
        else:
            status = 0
        msg = data['trade_state_desc']
        # SUCCESS—支付成功
        # REFUND—转入退款
        # NOTPAY—未支付
        # CLOSED—已关闭
        # REVOKED—已撤销（刷卡支付）
        # USERPAYING--用户支付中
        # PAYERROR--支付失败(其他原因，如银行返回失败)
        device_info = data['device_info']  # 微信支付分配的终端设备号
        trade_type = data['trade_type']  # 交易类型
        bank_type = data['bank_type']  # 付款银行
        fee_type = data['fee_type']  # 货币种类
        cash_fee = data['cash_fee']  # 现金支付金额(分)
        # cash_fee_type = data['cash_fee_type']  # 现金支付货币类型
        # nonce_str = data['nonce_str']  # 随机字符串
        # coupon_fee = data['coupon_fee']  # 代金券金额
        # coupon_count = data['coupon_count']  # 代金券使用数量
        # coupon_id_$n = data['coupon_id_$n']  # 代金券ID
        # coupon_fee_$n = data['coupon_fee_$n']  # 单个代金券支付金额

        update_sql = ''' update orders set app_id='{app_id}', 
                            seller_id='{seller_id}', buyer_id='{buyer_id}', total_amount='{total_amount}', 
                            out_trade_no='{out_trade_no}', gmt_create='{gmt_create}', trade_no='{trade_no}', 
                            device_info='{device_info}', trade_type='{trade_type}', bank_type='{bank_type}', 
                            fee_type='{fee_type}', cash_fee='{cash_fee}', 
                            status='{status}', 
                            trade_status='{trade_status}' where out_trade_no='{out_trade_no}'  '''
        update_sql = update_sql.format(
            trade_status=trade_status,
            app_id=app_id,
            seller_id=seller_id,
            buyer_id=buyer_id,
            total_amount=total_amount,
            out_trade_no=out_trade_no,
            gmt_create=gmt_create,
            trade_no=trade_no,
            device_info=device_info,
            trade_type=trade_type,
            bank_type=bank_type,
            fee_type=fee_type,
            cash_fee=cash_fee,
            status=status
            # err_code_des=err_code_des,
            # err_code=err_code
        )
        cur_dict.execute(update_sql)
    else:
        msg = trade_status
        status = 0
        update_sql = '''update {table} set  
        trade_status='{trade_status}', app_id='{app_id}', seller_id='{seller_id}', status='{status}' 
        where id={id} and status!=1 '''
        update_sql = update_sql.format(
            # err_code=err_code,
            # err_code_des=err_code_des,
            trade_status=trade_status,
            app_id=app_id,
            seller_id=seller_id,
            id=id,
            status=status
        )
        cur_dict.execute(update_sql)
    conn.commit()
    return status, msg


def make_querypayment_request(params_dict, query_order_url):
    """
    生成查询订单返回的数据参数
    """

    def generate_nonce_str():
        """
        生成随机字符串
        """
        return str(uuid.uuid4()).replace('-', '')

    def generate_sign(params):
        """
        生成md5签名的参数
        """
        if 'sign' in params:
            params.pop('sign')
        src = '&'.join(['%s=%s' % (k, v) for k, v in sorted(params.items())]) + '&key=%s' % WEIXIN_KEY
        return md5(src.encode('utf-8')).hexdigest().upper()

    def generate_request_data(params_dict):
        """
        生成统一下单请求所需要提交的数据
        """
        params_dict['nonce_str'] = generate_nonce_str()
        params_dict['sign'] = generate_sign(params_dict)
        return xmltodict.unparse({'xml': params_dict}, pretty=True, full_document=False).encode('utf-8')

    data = generate_request_data(params_dict)
    headers = {'Content-Type': 'application/xml'}
    res = requests.post(query_order_url, data=data, headers=headers)
    if res.status_code == 200:
        result = json.loads(json.dumps(xmltodict.parse(res.content)))
        # if result['xml']['return_code'] == 'SUCCESS':
        #     prepay_id = result['xml']['prepay_id']
        #     return generate_call_app_data(params_dict, prepay_id)
        # else:
        return result['xml']
    return None


def weixin_orderquery(request):
    """
    【API】:支付状态查询,供商户客户端app调用
    """
    res = {
        'code': 1,
        'status': 0,
        'msg': '支付失败！未知错误！'
    }
    out_trade_no = request.POST.get('out_trade_no')  # 商户订单号
    try:
        select_sql = '''select id, app_id, trade_no, seller_id, status from orders 
        where out_trade_no={out_trade_no} '''
        select_sql = select_sql.format(out_trade_no=out_trade_no)
        cur_dict.execute(select_sql)
        order_data = cur_dict.fetchone()
        if order_data:
            id = order_data['id']
            # 支付成功
            if order_data['status'] == 1:
                res['status'] = 1
                res['msg'] = '支付成功!'
            # 支付失败
            elif order_data['status'] == 0:
                res['status'] = 0
                res['msg'] = '支付失败!'
            # 支付过程中, 查询微信服务器支付状态
            else:
                params_dict = {
                    'appid': order_data['app_id'],
                    'mch_id': order_data['seller_id'],
                    'transaction_id': order_data['trade_no']
                }
                data = make_querypayment_request(params_dict, WEIXIN_QUERY_ORDER_URL)
                if data:
                    if data['return_code'] == 'SUCCESS':
                        trade_status = data['result_code']  # 业务结果  SUCCESS/FAIL
                        if trade_status == "SUCCESS":
                            res['status'], res['msg'] = update_order(data)
                        elif trade_status == "ORDERNOTEXIST":
                            res['msg'] = "支付错误! 微信服务器返回的订单号不存在！"
                            res['status'] = 0
                        elif trade_status == "SYSTEMERROR":
                            res['msg'] = "支付错误! 微信服务器错误！"
                            res['status'] = 0
                        else:
                            res['status'] = 0
                            res['msg'] = "支付错误! 微信服务器支付错误！"
                    else:
                        res['status'] = 0
                        res['msg'] = data['return_msg']

                else:
                    res['msg'] = "支付错误! 微信服务器通信错误！"
        else:
            res['status'] = 0
            res['msg'] = "订单号不存在！"
    except Exception:
        traceback.print_exc()
    finally:
        return json.dumps(res)
