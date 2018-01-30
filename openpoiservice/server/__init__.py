# openpoiservice/server/__init__.py


import os

from flask import Flask, render_template
from flask_bcrypt import Bcrypt
from flask_debugtoolbar import DebugToolbarExtension
from flask_sqlalchemy import SQLAlchemy

# instantiate the extensions
bcrypt = Bcrypt()
toolbar = DebugToolbarExtension()
db = SQLAlchemy()


def create_app():
    # instantiate the app
    app = Flask(
        __name__
    )

    # set config
    app_settings = os.getenv('APP_SETTINGS', 'openpoiservice.server.config.ProductionConfig')
    app.config.from_object(app_settings)

    # set up extensions
    bcrypt.init_app(app)
    toolbar.init_app(app)
    db.init_app(app)

    # register blueprints
    from openpoiservice.server.main.views import main_blueprint
    app.register_blueprint(main_blueprint)

    # error handlers
    @app.errorhandler(401)
    def unauthorized_page(error):
        return render_template('errors/401.html'), 401

    @app.errorhandler(403)
    def forbidden_page(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error_page(error):
        return render_template('errors/500.html'), 500

    return app
