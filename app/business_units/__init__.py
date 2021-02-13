from flask import Blueprint

business_units = Blueprint('business_units', __name__)

from . import business_untis_api
