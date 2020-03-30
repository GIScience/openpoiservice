# openpoiservice/server/__init__.py

from flask import Flask, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from flasgger import Swagger
from flask_cors import CORS
from openpoiservice.utils.categories import CategoryTools
from openpoiservice.api import api_exceptions
import yaml
import os
import time
import logging

logger = logging.getLogger(__name__)

# instantiate the extensions

"""load custom settings for openpoiservice"""
basedir = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(basedir, '..', 'conf/config.yml')) as f:
    ops_settings = yaml.safe_load(f)
    if os.environ.get('POSTGRES_HOST'):
        ops_settings['provider_parameters']['host'] = os.environ.get('POSTGRES_HOST')
    if os.environ.get('POSTGRES_DBNAME'):
        ops_settings['provider_parameters']['db_name'] = os.environ.get('POSTGRES_DBNAME')
    if os.environ.get('POSTGRES_PORT'):
        ops_settings['provider_parameters']['port'] = os.environ.get('POSTGRES_PORT')
    if os.environ.get('POSTGRES_USER'):
        ops_settings['provider_parameters']['user_name'] = os.environ.get('POSTGRES_USER')
    if os.environ.get('POSTGRES_PASS'):
        ops_settings['provider_parameters']['password'] = os.environ.get('POSTGRES_PASS')
    if os.environ.get('APP_SETTINGS') == 'testing':
        ops_settings['provider_parameters']['table_name'] += '_tests'


config_map = {
    'development': 'conf.config_flask.DevelopmentConfig',
    'production': 'conf.config_flask.ProductionConfig',
    'testing': 'conf.config_flask.TestingConfig'
}

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
    app_settings = os.getenv('APP_SETTINGS', 'production')
    app.config.from_object(config_map[app_settings])

    # set up extensions
    db.init_app(app)

    # register blueprints
    from openpoiservice.api.views import main_blueprint
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

    # shell context for flask cli
    app.shell_context_processor({
        'app': app,
        'db': db}
    )

    return app
