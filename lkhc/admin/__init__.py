from flask import Blueprint

bp = Blueprint('admin', __name__)

from lkhc.admin import routes

