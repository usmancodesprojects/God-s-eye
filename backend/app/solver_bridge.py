"""The ONLY project-specific integration point for Huzaifa's code.

Set SOLVER_CALLABLE=your_package.adapter:optimize in backend/.env.
The callable must be synchronous and return the documented JSON dict.
See docs/SOLVER_HANDOFF.md. No optimization is implemented here.
"""
import importlib
import inspect
import os
from functools import lru_cache
from typing import Callable


@lru_cache(maxsize=1)
def get_solver() -> Callable | None:
    path = os.getenv('SOLVER_CALLABLE', '').strip()
    if not path:
        return None
    module_name, separator, function_name = path.partition(':')
    if not separator or not module_name or not function_name:
        raise RuntimeError('SOLVER_CALLABLE must have the form package.module:function')
    function = getattr(importlib.import_module(module_name), function_name)
    if not callable(function) or inspect.iscoroutinefunction(function):
        raise RuntimeError('SOLVER_CALLABLE must identify a synchronous function')
    return function
