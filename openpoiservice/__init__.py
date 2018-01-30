# openpoiservice/__init__.py

import yaml
import os

basedir = os.path.abspath(os.path.dirname(__file__))

# load custom settings for openpoiservice
ops_settings = yaml.safe_load(open(os.path.join(basedir, 'ops_settings.yml')))
