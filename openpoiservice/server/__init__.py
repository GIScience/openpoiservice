# openpoiservice/server/__init__.py


import os

from flask import Flask, jsonify
from flask_debugtoolbar import DebugToolbarExtension
from flask_sqlalchemy import SQLAlchemy
from openpoiservice.server.categories import CategoryTools

# instantiate the extensions
toolbar = DebugToolbarExtension()
db = SQLAlchemy()

# load categories
categories_tools = CategoryTools('categories.yml')


def create_app():
    # instantiate the app
    app = Flask(
        __name__
    )

    # set config
    app_settings = os.getenv('APP_SETTINGS', 'openpoiservice.server.config.ProductionConfig')
    app.config.from_object(app_settings)

    # set up extensions
    toolbar.init_app(app)
    db.init_app(app)

    # register blueprints
    from openpoiservice.server.main.views import main_blueprint
    app.register_blueprint(main_blueprint)

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

    return app
