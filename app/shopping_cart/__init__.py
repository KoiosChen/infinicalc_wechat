from flask import Blueprint

shopping_cart = Blueprint('shopping_cart', __name__)

from . import shopping_cart_api
