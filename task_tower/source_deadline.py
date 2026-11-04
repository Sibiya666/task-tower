"""Scoped monotonic source budget; the process guardian owns hard teardown."""
from contextlib import contextmanager
from contextvars import ContextVar
import math
import time

_deadline=ContextVar('task_tower_source_deadline',default=None)


def remaining(default):
    deadline=_deadline.get()
    if deadline is None:return default
    value=deadline-time.monotonic()
    if value<=0:raise ValueError('Source operation deadline exceeded')
    return min(default,value)


@contextmanager
def source_deadline(deadline):
    if type(deadline) not in (int,float) or not math.isfinite(deadline):raise ValueError('Invalid source deadline')
    previous=_deadline.get()
    token=_deadline.set(deadline if previous is None else min(previous,deadline))
    try:
        remaining(30)
        yield
        remaining(30)
    finally:_deadline.reset(token)
