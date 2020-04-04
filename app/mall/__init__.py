from flask import Blueprint

mall = Blueprint('mall', __name__)

from . import mall_api, brands, sku, classifies, standards, spu
