# openpoiservice/server/utils/decorators.py

import time
import logging
import cProfile
import functools
import os
import sys
import inspect

logger = logging.getLogger(__name__)


def timeit(method):
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        logger.info(f'{method.__name__} took {round((te - ts) * 1000, 2)} ms')
        return result

    return timed
