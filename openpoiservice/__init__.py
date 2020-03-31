# openpoiservice/server/__init__.py

from flask import Flask, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from flasgger import Swagger
from flask_cors import CORS
import yaml
import os
import time
import logging

from openpoiservice.__version__ import __version__
from openpoiservice.utils.categories import CategoryTools
from openpoiservice.api import api_exceptions

logger = logging.getLogger(__name__)

config_map = {
    'development': 'config.DevelopmentConfig',
    'production': 'config.ProductionConfig',
    'testing': 'config.TestingConfig'
}

db = SQLAlchemy()

# load categories
categories_tools = CategoryTools('categories.yml')


def create_app(script_info=None):
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
    app_settings = os.getenv('FLASK_ENV')
    logger.info(os.getenv('FLASK_ENV'))
    app.config.from_object(config_map[app_settings])
    logger.info(app_settings)
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
