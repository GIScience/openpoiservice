# openpoiservice/server/utils/decorators.py

import time
import logging
import cProfile
import functools
import os
import sys
import inspect
import traceback
from functools import wraps
from multiprocessing import Process, Queue

logger = logging.getLogger(__name__)


def processify(func):
    """Decorator to run a function as a process.
    Be sure that every argument and the return value
    is *pickable*.
    The created process is joined, so the code does not
    run in parallel."""

    def process_func(q, *args, **kwargs):
        try:
            ret = func(*args, **kwargs)
        except Exception:
            ex_type, ex_value, tb = sys.exc_info()
            error = ex_type, ex_value, ''.join(traceback.format_tb(tb))
            ret = None
        else:
            error = None

        q.put((ret, error))

    # register original function with different name
    # in sys.modules so it is pickable
    process_func.__name__ = func.__name__ + 'processify_func'
    setattr(sys.modules[__name__], process_func.__name__, process_func)

    @wraps(func)
    def wrapper(*args, **kwargs):
        q = Queue()
        p = Process(target=process_func, args=[q] + list(args), kwargs=kwargs)
        p.start()
        ret, error = q.get()

        if error:
            ex_type, ex_value, tb_str = error
            raise RuntimeError(f"{ex_type} in {func}: {ex_value}, {tb_str}")

        return ret

    return wrapper


def get_size(obj, seen=None):
    """Recursively finds size of objects in bytes"""
    size = sys.getsizeof(obj)
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    # Important mark as seen *before* entering recursion to gracefully handle
    # self-referential objects
    seen.add(obj_id)
    if hasattr(obj, '__dict__'):
        for cls in obj.__class__.__mro__:
            if '__dict__' in cls.__dict__:
                d = cls.__dict__['__dict__']
                if inspect.isgetsetdescriptor(d) or inspect.ismemberdescriptor(d):
                    size += get_size(obj.__dict__, seen)
                break
    if isinstance(obj, dict):
        size += sum((get_size(v, seen) for v in obj.values()))
        size += sum((get_size(k, seen) for k in obj.keys()))
    elif hasattr(obj, '__iter__') and not isinstance(obj, (list, str, bytes, bytearray)):
        size += sum((get_size(i, seen) for i in obj))
    return size


def profile(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        try:
            profiler.enable()
            ret = func(*args, **kwargs)
            profiler.disable()
            return ret
        finally:
            filename = os.path.expanduser(
                os.path.join(os.getcwd(), func.__name__ + '.pstat')
            )
            profiler.dump_stats(filename)

    return wrapper


def timeit(method):
    def timed(*args, **kw):
        if len(args) == 1:
            operation = "Delete operations"
        else:
            operation = "File import" if isinstance(args[0], str) else f"Batch of {len(args[0])} files"
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        logger.info(f"{operation} completed in {int((te - ts) // 3600):02}:{int(((te - ts) % 3600) // 60):02}:{int((te - ts) % 60):02} ({round((te - ts) * 1000, 2)} ms)")
        return result

    return timed
