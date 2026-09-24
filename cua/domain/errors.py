"""The one base every error this package raises on purpose derives from.

A tool catches CuaError at the top and prints its message; anything else is a bug
and keeps its traceback.
"""


class CuaError(Exception):
    pass
