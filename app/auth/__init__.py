from flask import Blueprint
from authlib.integrations.flask_client import OAuth

oauth = OAuth()
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

from . import routes  # noqa: E402,F401