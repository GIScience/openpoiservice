# openpoiservice/server/config_flask.py

import os

from openpoiservice import ops_settings

pg_settings = ops_settings['provider_parameters']

class BaseConfig(object):
    """Base configuration."""

    # SECRET_KEY = 'my_precious'
    WTF_CSRF_ENABLED = True
    DEBUG_TB_ENABLED = False
    DEBUG_TB_INTERCEPT_REDIRECTS = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # SECRET_KEY = 'my_precious'
    SQLALCHEMY_DATABASE_URI = 'postgresql://{}:{}@{}:{}/{}'.format(pg_settings['user_name'], pg_settings['password'],
                                                                   pg_settings['host'], pg_settings['port'],
                                                                   pg_settings['db_name'])


class ProductionConfig(BaseConfig):
    """Production configuration."""
    pass


class DevelopmentConfig(BaseConfig):
    """Production configuration."""

    DEBUG_TB_ENABLED = True


class TestingConfig(BaseConfig):
    """Testing configuration."""
    pass
