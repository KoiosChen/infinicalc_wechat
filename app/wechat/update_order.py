from app import db, logger
from app.models import ShopOrders, make_order_id
import datetime
from app.common import submit_return, session_commit
from app.public_method import new_data_obj
from app.rebates import calc_rebate


def update_it(data):
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
                    if session_commit().get("code") != 'success':
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

    return res
