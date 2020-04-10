from flask import Blueprint

sms = Blueprint('sms', __name__)

from . import send_sms, sms_api
