# openpoiservice/server/__init__.py

from flask import Flask, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from flasgger import Swagger
from flask_cors import CORS
from openpoiservice.server.categories.categories import CategoryTools
from openpoiservice.server.api import api_exceptions
import yaml
import os
import time
import logging

logger = logging.getLogger(__name__)

# instantiate the extensions

"""load custom settings for openpoiservice"""
basedir = os.path.abspath(os.path.dirname(__file__))
ops_settings = yaml.safe_load(open(os.path.join(basedir, 'ops_settings.yml')))

if "TESTING" in os.environ:
    ops_settings['provider_parameters']['table_name'] = ops_settings['provider_parameters']['table_name'] + '_test'

db = SQLAlchemy()

# load categories
categories_tools = CategoryTools('categories.yml')


def create_app(script_info=None):
    # instantiate the app

    app = Flask(
        __name__
    )
    cors = CORS(app, resources={r"/pois/*": {"origins": "*"}})

    app.config['SWAGGER'] = {
        'title': 'Openpoiservice',
        "swagger_version": "2.0",
        'version': 0.1,
        'uiversion': 3
    }


    # set config
    app_settings = os.getenv('APP_SETTINGS', 'openpoiservice.server.config.ProductionConfig')
    app.config.from_object(app_settings)

    # set up extensions
    db.init_app(app)

    # register blueprints
    from openpoiservice.server.api.views import main_blueprint
    app.register_blueprint(main_blueprint)

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

    # error handlers
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
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response

    # shell context for flask cli
    app.shell_context_processor({
        'app': app,
        'db': db}
    )

    return app
