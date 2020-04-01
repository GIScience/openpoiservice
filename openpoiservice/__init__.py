# openpoiservice/server/__init__.py

from flask import Flask, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from flasgger import Swagger
from flask_cors import CORS

import os
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

from .__version__ import __version__
from .logger import logger
from .utils.categories import CategoryTools
from .api import api_exceptions

# Load all envs if called from outside flask context
this_path = Path(os.path.dirname(__file__))
dotenv_path = os.path.join(this_path.parent, '.env')
flaskdotenv_path = os.path.join(this_path.parent, '.flaskenv')
if os.path.exists(dotenv_path):
    load_dotenv(flaskdotenv_path)
    load_dotenv(dotenv_path)

config_map = {
    'development': 'config_flask.DevelopmentConfig',
    'production': 'config_flask.ProductionConfig',
    'testing': 'config_flask.TestingConfig'
}

db = SQLAlchemy()

# load categories
categories_tools = CategoryTools('config_categories.yml')


def create_app():
    # instantiate the app

    app = Flask(
        __name__
    )

    CORS(app, resources={r"/pois/*": {"origins": "*"}})

    app.config['SWAGGER'] = {
        'title': 'Openpoiservice',
        "swagger_version": "2.0",
        'version': __version__,
        'uiversion': 3
    }

    # set config
    app_settings = os.getenv('FLASK_ENV', 'production')
    app.config.from_object(config_map[app_settings])

    # Set logger verbosity
    log_level = app.config.get('OPS_LOGGING')
    if log_level:
        if 'Level' in str(logging.getLevelName(log_level.upper())):
            logger.warning(f"OPS_LOGGING variable has invalid value {log_level}. Continuing with INFO.")
        else:
            logger.info(f"Logging level set to {log_level}")
            logger.setLevel(log_level.upper())

    # set up extensions
    db.init_app(app)
    Swagger(app, template_file='api/pois_post.yaml')

    if "DEVELOPMENT" in os.environ:
        @app.before_request
        def before_request():
            g.start = time.time()

        @app.teardown_request
        def teardown_request(exception=None):
            # if 'start' in g:
            diff = time.time() - g.start
            logger.info("Request took: {} seconds".format(diff))

    # _error handlers
    @app.errorhandler(401)
    def unauthorized_page(error):
        return jsonify({"error_message": 401})

    @app.errorhandler(403)
    def forbidden_page(error):
        return jsonify({"error_message": 403})

    @app.errorhandler(404)
    def page_not_found(error):
        return jsonify({"error_message": 404})

    @app.errorhandler(500)
    def server_error_page(error):
        return jsonify({"error_message": 500})

    @app.errorhandler(api_exceptions.InvalidUsage)
    def handle_invalid_usage(error):
        response_obj = {
            "error": error.to_dict()
        }
        response = jsonify(response_obj)
        response.status_code = error.status_code
        return response

    # Register blueprint
    from openpoiservice.api.routes import main_bp
    app.register_blueprint(main_bp)

    # shell context for flask cli
    app.shell_context_processor({
        'app': app,
        'db': db}
    )

    return app
