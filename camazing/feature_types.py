import abc

from genicam2.genapi import IBoolean, IEnumeration, IInteger, IFloat, \
                            IString, ICommand
from .util import to_bool


class AccessModeError(Exception):
    pass


class Feature(abc.ABC):
    """A base class for GenICam GenApi node wrappers."""

    def __init__(self, feature):
        """Initialize the wrapper.

        Params
        ------
        feature
            GenICam GenApi node (e.g. IEnumeration or IInteger)
        """
        self._feature = feature
        self.name = feature.node.display_name
        self.description = feature.node.description
        self._exclude_from_info = ['info']
    def _getinfo(self, attr):
            try:
                return self.__getattribute__(attr)
            except Exception:
                return None

    def info(self):
        return {k: self._getinfo(k) for k in super().__dir__()
                if not k.startswith('_') and k not in self._exclude_from_info}

    @property
    def access_mode(self):
        """Get access mode of the feature.

        Returns
        -------
        access_mode : {'', 'r', 'w', 'rw'}
            Access mode of the feature.
            '': Feature is not accessable
            'r': Feature is read-only
            'w': Feature is write-only
            'rw' Feature is readable and writable
        """
        access_mode = self._feature.get_access_mode()
        if access_mode == 1:
            return ""
        elif access_mode == 2:
            return "w"
        elif access_mode == 3:
            return "r"
        elif access_mode == 4:
            return "rw"
        else:
            raise Exception("Unexpected access mode")

class Bounded(abc.ABC):
    """A base class for features that are numeric values."""

    @property
    def min(self):
        """Gives the minimum value of the feature.

        Returns
        -------
        int or float
            The minimum value of the feature.
        """
        return self._feature.min

    @property
    def max(self):
        """Gives the maximum value of the feature.

        Returns
        -------
        int or float
            The maximum value of the feature.
        """
        return self._feature.max

    def _check_if_in_range(self, value):
        """Raises an exception if `value` is not between `min` and `max`.

        Parameters
        ----------
        value : int or float

        Raises
        ------
        ValueError
            If `value` is not between range [`min`, `max`].
        """
        if value < self.min or value > self.max:
            raise ValueError(f"'{self.name}' expected a number between "
                             f"({self.min}, {self.max}) but got {value}.")


class Valuable(Feature, abc.ABC):
    """a base class for features with value."""

    def __init__(self, feature):
        Feature.__init__(self, feature)

    @abc.abstractmethod
    def _set_value(self):
        pass

    @property
    def value(self):
        """Gets the current value of the feature.

        Raises
        ------
        AccessModeError
            If the feature is not readable.

        Returns
        -------
        The current value of the feature.
        """
        if "r" in self.access_mode:
            return self._feature.value
        else:
            message = "Cannot get value of '{}', because the feature ".format(
                self.name
            )
            if "w" in self.access_mode:
                message += "is write-only."
            else:
                message += "is not accessible."
            raise AccessModeError(message)

    @value.setter
    def value(self, value):
        """Sets the current value of the feature.

        Parameters
        ----------
        value
            The value that will be set as a current value.

        Raises
        ------
        AccessModeError
            If the feature is not writable.
        ValueError
            If the given value is invalid in any way.
        """
        if "w" in self.access_mode:
            self._set_value(value)
        else:
            message = "Cannot set value of '{}', because the feature ".format(
                self.name
            )
            if "r" in self.access_mode:
                message += "is read-only."
            else:
                message += "is not accessible."
            raise AccessModeError(message)


class Boolean(Valuable):
    """A wrapper class for IBoolean GenApi node."""

    def __init__(self, feature):
        Valuable.__init__(self, feature)

    def _set_value(self, value):
        value = to_bool(value)
        self._feature.value = value


class Command(Feature):
    """A wrapper class for ICommand GenApi node."""

    def __init__(self, feature):
        Feature.__init__(self, feature)
        self._exclude_from_info.append('execute')

    def execute(self):
        self._feature.execute()


class Enumeration(Valuable):
    """A wrapper class for IEnumeration GenApi node."""

    def __init__(self, feature):
        Valuable.__init__(self, feature)

    def _set_value(self, value):
        if value not in self.valid_values:
            raise ValueError(f"'{self.name}' expected one of "
                             f"{self.valid_values} but got {value}.")
        self._feature.value = value

    @property
    def valid_values(self):
        """Gives a tuple containing all of the valid values. The enumeration
        doesn't accept any value that is not included in this tuple.

        Returns
        -------
        tuple
            A tuple containing all of the valid values.
        """
        return self._feature.symbolics


class Integer(Valuable, Bounded):
    """A wrapper class for IInteger GenApi node."""

    def __init__(self, feature):
        Valuable.__init__(self, feature)

    def _set_value(self, value):
        value = int(value)
        self._check_if_in_range(value)
        self._feature.value = value

    @property
    def increment(self):
        """

        Returns
        -------
        int
            An increment
        """
        return self._feature.inc


class Float(Valuable, Bounded):
    """A wrapper class for IFloat GenApi node."""

    def __init__(self, feature):
        Valuable.__init__(self, feature)

    def _set_value(self, value):
        value = float(value)
        self._check_if_in_range(value)
        self._feature.value = value

    @property
    def unit(self):
        """Gives a physical unit that is associated with the features value.

        Returns
        -------
        str
            A physical unit associated with the value. If the feature has no
            physical unit, an empty string is returned.
        """
        return self._feature.unit


class String(Valuable):
    """A wrapper class for IString GenApi node."""

    def __init__(self, feature):
        Valuable.__init__(self, feature)

    def _set_value(self, value):
        value = str(value)
        self._feature.value = value


mapping = {
    IBoolean: Boolean,
    IEnumeration: Enumeration,
    IInteger: Integer,
    IFloat: Float,
    IString: String,
    ICommand: Command
}
