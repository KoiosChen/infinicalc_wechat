from flask import Blueprint

scene_invitation = Blueprint('scene_invitation', __name__)

from . import scene_invitation_api
