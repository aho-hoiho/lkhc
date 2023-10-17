from flask import Blueprint

bp = Blueprint('main', __name__)

from lkhc.main import routes
