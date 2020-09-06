from flask import Blueprint

item_orders = Blueprint('item_orders', __name__)

from . import item_orders_api
