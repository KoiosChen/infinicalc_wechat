from flask import Blueprint

promotions = Blueprint('promotions', __name__)

from . import promotions_api, coupons, special_group_purchase_promotion
