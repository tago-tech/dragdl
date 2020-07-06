from functools import wraps
import time
import datetime


def SimpleInvokeLoger(func):
    @wraps(func)
    def wrappedFunc(*args, **kwargs):
        postFixed = str(datetime.datetime.now()) + '.'
        print('[{} Invoke - {}].'.format(postFixed,func.__name__))
        result = func(*args, **kwargs)
        return result
    return wrappedFunc

