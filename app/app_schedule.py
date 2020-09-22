from app.public_method import order_cancel, submit_return
from app.models import ShopOrders
from app import logger
import datetime


def check_orders():
    shop_orders = ShopOrders.query.filter(ShopOrders.is_pay.__ne__(1),
                                         ShopOrders.status.__ne__(0),
                                         ShopOrders.delete_at.__ne__(None),
                                          ShopOrders.create_at).all()

    for order in shop_orders:
        if datetime.datetime.now() - order.create_at > datetime.timedelta(hours=48):
            order_cancel("超时未支付", order.id)
            logger.info(f"{order.id} has been cancelled for pay timeout!")
