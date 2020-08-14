from flask import Blueprint

shopping_cart = Blueprint('shopping_cart', __name__)

from . import shop_cart_api, gifts
