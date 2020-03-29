from flask import Blueprint

mall = Blueprint('mall', __name__)

from . import mall_api, cart, commercial_tenant, coupon, items
