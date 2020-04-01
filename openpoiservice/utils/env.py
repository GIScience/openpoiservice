import os
from distutils.util import strtobool

def is_testing():
    try:
        is_testing = os.getenv('TESTING') if not os.getenv('TESTING', None) else strtobool(os.getenv('TESTING'))
    except ValueError as e:
        raise ValueError(f"TESTING env var has invalid value \"{os.getenv('TESTING')}\". Only truth values are allowed, such as 0, 1, on, off, True, False.")

    return is_testing
