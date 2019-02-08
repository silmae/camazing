"""Miscellaneous utility functions and classes."""


class Singleton(type):

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


def to_bool(value):
    """A slight modification of bool(). This function converts string literals
    'True' and 'False' to boolean values accordingly.

    Parameters
    ----------
    value
        The value to be converted to boolean.

    Raises
    ------
    ValueError
        If literal value is not convertible to boolean value.

    Returns
    -------
    bool
        The boolean value acquired after conversion.
    """
    if isinstance(value, str):
        if value == "True":
            return True
        elif value == "False":
            return False
        else:
            raise ValueError(f"Invalid literal for to_bool(): '{value}'")
    else:
        return bool(value)
