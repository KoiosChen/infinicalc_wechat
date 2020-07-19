from flask import Blueprint

express = Blueprint('express_address', __name__)

from . import express_address_api
