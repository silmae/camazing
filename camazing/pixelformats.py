import numpy as np


class PixelFormatError(Exception):
    pass


def get_valid_range(pxformat):
    """Return the valid range of values for a given pixel format.

    Parameters
    ----------
    pxformat: str
        Pixel format as given by cameras GenICam PixelFormat feature.

    Returns
    ------
    np.array
        A vector of [min_value, max_value] with the same type as the decoded
        pixel format.
    """
    try:
        valid_range = _ranges[pxformat]
    except KeyError:
        raise PixelFormatError(f'No range found for the pixel format `{pxformat}')

    return valid_range


def get_decoder(pxformat):
    """Return a numpy decoder for a given GenICam pixel format.

    Parameters
    ----------
    pxformat: str
        Pixel format as given by cameras PixelFormat.

    Returns
    -------
    decoder: function
        Function for decoding a buffer
    """
    try:
        decoder = _decoders[pxformat]
    except KeyError:
        raise PixelFormatError(f'No decoder for the pixel format `{pxformat}`')

    return decoder


def decode_raw(dtype):
    """Decode raw buffer with a given bit depth."""
    def decode(buf, shape):
        return np.frombuffer(
            buf,
            dtype=dtype
            ).reshape(*shape).copy()
    return decode


def decode_RGB(bpp):
    """Decode RGB buffer with a given bit depth."""
    def decode(buf, shape):
        return np.frombuffer(
            buf,
            dtype=bpp,
            ).reshape(*shape, 3).copy()
    return decode


def decode_YCbCr422_8():
    """Decode YCbCr422 buffer with given bit depth."""
    raise NotImplementedError


_decoders = {
    'BayerRG8': decode_raw(np.uint8),
    'BayerGB8': decode_raw(np.uint8),
    'BayerGB12': decode_raw(np.uint16),
    'BayerRG12': decode_raw(np.uint16),
    'BayerRG16': decode_raw(np.uint16),
    'RGB8': decode_RGB(np.uint8),
    'Mono8': decode_raw(np.uint8),
    'Mono16': decode_raw(np.uint16),
    }

_ranges = {
    'BayerRG8': np.uint8([0, 255]),
    'BayerGB8': np.uint8([0, 255]),
    'BayerGB12': np.uint16([0, 4095]),
    'BayerRG12': np.uint16([0, 4095]),
    'BayerRG16': np.uint16([0, 65535]),
    'RGB8': np.uint8([0, 255]),
    'Mono8': np.uint8([0, 255]),
    'Mono16': np.uint16([0, 65535]),
    }
