from flask import Blueprint

img_urls = Blueprint('img_urls', __name__)

from . import img_url
