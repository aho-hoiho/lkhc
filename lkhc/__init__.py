import json
import logging
import os

from flask import Flask

import lkhc.database

def create_app():
    app = Flask(__name__, instance_relative_config=True)

    fname = os.path.join(app.instance_path, "config.json")
    app.config.from_file(fname, load=json.load)

    fname = os.path.join(app.instance_path, "secrets.json")
    app.config.from_file(fname, load=json.load)
    app.secret_key = app.config['WEB_SESSION_SECRET']

    lkhc.database.db.init_app(app)
    with app.app_context():
        app.config['season'] = lkhc.database.season()
    
    # logging
    app.logger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler(os.path.join(app.instance_path,
                                                    app.config['LOG_DIR'],
                                                    app.config['LOG_FILE']))
    file_handler.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)   # logging.INFO
    fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(fmt)
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    app.logger.addHandler(file_handler)
#    app.logger.addHandler(console_handler)

    # Register blueprints
    from lkhc.main import bp as main_bp
    app.register_blueprint(main_bp)

    from lkhc.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    app.logger.info("lowkey started")
    return app

app = create_app()
