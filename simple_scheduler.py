#!/usr/bin/python
# -*- coding: utf-8 -*-

# built-in
import time
import sched
import datetime

from functools import wraps
from threading import Thread

def async(func):
    """
    Данный декоратор позволяет 
    выполнять простой метод ассинхронно
    """
    @wraps(func)
    def async_func(*args, **kwargs):
        func_hl = Thread(target=func, args=args, kwargs=kwargs)
        func_hl.start()
        return func_hl
    return async_func


def schedule(interval):
    """
    Данный декоратор позволяет выполнять 
    метод с указанной периодичностью в секундах
    """
    def decorator(func):
        def periodic(scheduler, interval, action, actionargs=()):
            scheduler.enter(interval, 1, periodic,
                            (scheduler, interval, action, actionargs))
            action(*actionargs)

        @wraps(func)
        def wrap(*args, **kwargs):
            scheduler = sched.scheduler(time.time, time.sleep)
            periodic(scheduler, interval, func)
            scheduler.run()
        return wrap
    return decorator