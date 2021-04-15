from flask import Blueprint

express_orders = Blueprint('express_orders', __name__)

from . import express_order_api
