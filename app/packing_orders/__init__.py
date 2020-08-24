from flask import Blueprint

packing_orders = Blueprint('packing_orders', __name__)

from . import packing_orders_api
