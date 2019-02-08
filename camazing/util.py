"""Miscellaneous utility functions and classes."""


class Singleton(type):

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


def expect_sorted(array):
    """Raises an exception if `array` if not a sorted list/array. Doesn't do
    anything otherwise.

    Raises
    ------
    ValueError
        If the given list/array is not sorted.
    """
    if not all([array[i] < array[i+1] for i in range(len(array) - 1)]):
        raise ValueError("Expected a sorted list/array, but the given "
                         "list/array is unsorted.")


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
