from flask import Blueprint

member_cards = Blueprint('member_cards', __name__)

from . import member_cards_api
