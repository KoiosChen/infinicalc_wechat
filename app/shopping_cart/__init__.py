from flask import Blueprint

shopping_cart = Blueprint('shopping_cart', __name__)

from . import place_order, gifts
