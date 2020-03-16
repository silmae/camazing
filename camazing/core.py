import atexit
import datetime as dt
import io
import logging
import os
import platform
import urllib
import sys
from functools import wraps

import genicam2.gentl as gtl
import genicam2.genapi as gapi
import numpy as np
import tabulate
import toml
import xarray as xr

import camazing.feature_types
from camazing.util import Singleton
from camazing.pixelformats import get_decoder, get_valid_range

# Some cameras are incompatible with zipfile package when Python version >= 3.7
if sys.version_info >= (3, 7):
    import zipfile36 as zipfile
else:
    import zipfile

# Initialize the logger.
logger = logging.getLogger(__name__)


class AcquisitionException(Exception):
    pass


def check_initialization(method):
    """Decorator for checking camera initialization.

    Checks that the `Camera` object is initialized by calling `is_initialized`
    before executing the given method.

    Parameters
    ----------
    method : method
        Method to execute with checks.

    Raises
    ------
    RuntimeError
        Raised when Camera is not initialized.

    """
    # If camera is not initialized, raise an error.
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self.is_initialized():
            raise RuntimeError(
                f"Cannot execute the function `{method.__name__}`, because "
                "the camera is not initialized."
            )
        return method(self, *args, **kwargs)

    return wrapper


def get_cti_file():
    """Tries to find an existing GenICam Producer file.

    The function checks if `GENICAM_GENTL[64|32]_PATH` environment variable
    (which is described in GenICam GenTL standard version 1.5, section 6.1.1)
    is set, and returns the path to the CTI file..

    Returns
    -------
    cti_file : str
        A path to GenICam Producer file.

    Raises
    ------
    OSError
        If environment variable `GENICAM_GENTL[64|32]_PATH` is not set.
    FileNotFoundError
        If GenICam Producer file (.cti) is not found.
    """
    logger.debug("Trying to find the CTI file automatically...")

    arch = platform.architecture()[0]  # Get the platform architecture.
    logger.debug(f"Platform architecture detected as {arch}")
    var = "GENICAM_GENTL64_PATH" if arch == "64bit" else "GENICAM_GENTL32_PATH"
    ctidir = os.getenv(var)  # Get the directory path in the environment variable.
    logger.debug(f"Looking for the CTI file in directory {ctidir}")

    if ctidir:  # Check that the environment variable contains the directory path.
        for ctifile in os.listdir(ctidir):
            # If `file` has extension `.cti`, we have found the CTI file.
            if ctifile.endswith(".cti"):
                filepath = os.path.join(ctidir, ctifile)
                logger.debug(
                    "Automatic lookup of CTI file was successful. Found "
                    "CTI file `{}` from environment variable `{}`.".format(
                        filepath,
                        var
                    )
                )
                return filepath
    else:
        # If environment variable is not set, raise an error.
        raise OSError(
            "Environment variable `{}` is not set.".format(var) +
            "Make sure you have a valid GenICam Producer installed."
        )

    # If execution reaches this point, file is not found and the following
    # error will be raised.
    raise FileNotFoundError(
        f"No GenICam Producer file (.cti) found from {var} environment "
        "variable."
    )


class CameraList(metaclass=Singleton):
    """List of all the cameras connected to the machine."""

    _headers = ["Vendor", "Model", "Serial number", "TL type"]

    def __init__(self, cti_file=None):
        """Initializes the `CameraList`.

        Parameters
        ----------
        cti_file : str, optional
            Path to the GenICam Producer file (.cti). If no file path is given,
            automatic lookup of the Producer file is performed.
        """
        # If GenICam Producer file is not given as an argument, try to find an
        # existing one automatically.
        if cti_file is None:
            # `get_cti_file` contains logging, so no need to do it here.
            self._cti_file = get_cti_file()
        else:
            logger.debug(
                "File path to CTI file was provided by the user: `{}`".format(
                    cti_file
                )
            )
            self._cti_file = cti_file

        # Initialize the GenICam Producer.
        self._producer = gtl.GenTLProducer.create_producer()
        self._producer.open(self._cti_file)
        logger.debug(
            "Initialized GenICam Producer, which is compliant with version "
            "{} of the GenICam GenTL standard.".format(
                self._producer.get_compliant_version()
            )
        )

        # Initialize the system (see section 2.2.1 in GenICam GenTL standard,
        # version 1.5).
        self._system = self._producer.create_system()
        self._system.open()
        logger.debug("Initialized GenICam System: `{}`.".format(
            self._system.display_name
        ))

        # Interface info list has all available interfaces listed. Update it.
        self._system.update_interface_info_list(200)  # Timeout is 200 ms.

        # Initialize the interfaces (see section 2.2.2 in GenICam GenTL
        # standard, version 1.5).
        self._interfaces = []
        for interface_info in self._system.interface_info_list:
            interface = interface_info.create_interface()
            self._interfaces.append(interface)
            if not interface.is_open():
                interface.open()
                logger.debug(
                    "Initialized {} interface: `{}`.".format(
                        interface.tl_type,  # Transport Layer Type
                        interface.id_  # ID
                    )
                )

        # Update the list of available cameras.
        self.update()

    def __del__(self):
        """Free up the resources by closing all open interfaces, the system
        and the producer.
        """
        for interface in self._interfaces:
            logger.debug(
                "Closing {} interface: `{}`.".format(
                    interface.tl_type,  # Transport Layer type
                    interface.id_  # ID
                )
            )
            interface.close()

        self._system.close()
        logger.debug("Deinitialized GenICam System.")
        self._producer.close()
        logger.debug("Deinitialized GenICam Producer.")

    def __repr__(self):
        """Get nice representation of the `CameraList`.

        Returns
        -------
        str
            Tabular representation of the `CameraList`.
        """
        return tabulate.tabulate(
            self._repr_items,
            self._headers,
            tablefmt="fancy_grid",
            showindex="always"
        )

    def _repr_html_(self):
        """Get a HTML representation of the `CameraList`.

        Returns
        -------
        str
            A HTML representation of the `CameraList`.

        Notes
        -----
        This method is mainly used by Jupyter Notebook.
        """
        return tabulate.tabulate(
            self._repr_items,
            self._headers,
            tablefmt="html",
            showindex="always"
        )

    def __iter__(self):
        """Get iterator for `CameraList`.

        Returns
        -------
        A new iterator based on the `CameraList`.
        """
        return iter(self._cameras)

    def __len__(self):
        """Get length of the `CameraList`.

        Returns
        -------
        int
            Length of the `CameraList`, or number of cameras in the list.
        """
        return len(self._cameras)

    def __getitem__(self, index):
        """Get a `Camera` from the `CameraList`.

        Parameters
        -------
        index : int
            A list index (just like in regular Python lists).

        Returns
        -------
        Camera
            A `Camera` object.
        """
        return self._cameras[index]

    def update(self):
        """Update the list of available cameras."""
        logger.debug("Trying to update the camera list...")

        self._device_infos = []  # Reset device infos.

        # Update device info lists in case of newly connected cameras.
        for interface in self._interfaces:
            interface.update_device_info_list(200)
            self._device_infos.extend(interface.device_info_list)

        # self._cameras = [Camera(di) for di in self._device_infos]
        # logger.info("Updated the list of cameras.")

        self._cameras = []  # Reset the list of cameras.
        self._repr_items = []  # Reset the representable camera info.

        for device_info in self._device_infos:
            self._cameras.append(Camera(device_info))
            self._repr_items.append([
                device_info.vendor,
                device_info.model,
                device_info.serial_number,
                device_info.tl_type
            ])

    @property
    def cti_file(self):
        """CTI file used to detect cameras."""
        return self._cti_file


class Camera:

    class _Port(gapi.AbstractPort):
        """A concrete implementation of port."""

        def __init__(self, port):
            """Initialize the port.

            Parameters
            ----------
            port
                Remote port of an device info object.
            """
            gapi.AbstractPort.__init__(self)
            self._port = port

        def read(self, address, size):
            """Read number of bytes from the port.

            Parameters
            ----------
            address : int
                Memory address from which we start reading the bytes.
            size : int
                Number of bytes to read.
            """
            buffer = self._port.read(address, size)
            return buffer[1]

        def write(self, address, value):
            """Write number of bytes to the port.

            Parameters
            ----------
            address : int
                Memory address from which we start writing the bytes.
            size : int
                Number of bytes to write.
            """
            self._port.write(address, value)

        def get_access_mode(self):
            """Get the access mode of a node."""
            return gapi.EAccessMode.RW

    def __init__(self, device_info):
        """Initialize Camera object.

        Parameters
        ----------
        device_info : genicam2.genapi.IDeviceInfo
            GenICam DeviceInfo object.

        Notes
        -----
        This function doesn't not initialize the camera itself (that can be
        achieved with the `initialize` method). The benefit of this is that we
        can have many Camera objects (for example in the `CameraList`) without
        reserving any resources for the camera internals, and we can reserve
        the resources only when needed.
        """
        self._device_info = device_info
        self._device = device_info.create_device()

        # Needs to be defined in order to get `finalize` method working.
        self._node_map = None

        # Needs to be defined here in order to get `is_acquiring` method
        # working.
        self._is_acquiring = False

        # Make sure that `finalize` is called when one exits the program.
        atexit.register(self.finalize)

    def __del__(self):
        """Does clean up when `Camera` object is deleted."""
        self.finalize()

    def __enter__(self):
        """Initializes camera (if not already initialized) and starts the
        image acquisition.
        """
        # Initialize the camera when `Camera` object is created for the first
        # time by using context manager. Otherwise won't do anything.
        self.initialize()

        # If acquisition has not been started, start acquisition.
        # Otherwise this won't do anything.
        self.start_acquisition()

        return self

    def __exit__(self, exception_type, exception_value, traceback):
        """Stops the acquisition after leaving the runtime context."""
        self.stop_acquisition()

    def __repr__(self):
        """More useful representation for the `Camera` object.

        Shows the camera vendor, model, serial number and firmware version.

        Notes
        -----
        If someone is concerned that one cannot see the `Camera` object id
        anymore, there is the `id` function for that.
        """
        return "\n".join(
            ["Vendor: " + self._device_info.vendor,
             "Model: " + self._device_info.model,
             "Serial number: " + self._device_info.serial_number,
             "Firmware version: " + self._device_info.tl_type]
        )

    @check_initialization
    def __getitem__(self, item):
        """Get a feature from the `features` dictionary.

        This enables the user to use shortcut notation, e.g.
        `camera['Gain'].value` instead of `camera.feature['Gain'].value`.

        Parameters
        ----------
        item : str
            A feature name, that will be used to fetch the feature from the
            dictionary.

        Raises
        ------
        KeyError
            If `item` is not found from `features`.
        """
        return self._features[item]

    @check_initialization
    def __contains__(self, item):
        """Checks if `item` is in `features` dictionary.

        bool
            `True` if key is in the `features` dictionary. Otherwise `False`.
        """
        return item in self._features

    @check_initialization
    def keys(self):
        """Get a view of dictionary keys (names of the available features).

        Returns
        -------
        dict_keys
            A view of dictionary keys, or names of the available features.
        """
        return self._features.keys()

    @check_initialization
    def features(self):
        """Get a view of feature objects.

        Returns
        -------
        dict_values
            A view of feature objects.

        Notes
        -----
        This is same as `values()` in regular dictionaries. The `features` name
        is used to avoid confusion, that `values()` would return the actual
        values of the features.
        """
        return self._features.values()

    @check_initialization
    def items(self):
        """Get a view of cameras items.

        Returns
        -------
        dict_items
            A view of cameras items.
        """
        return self._features.items()

    def is_initialized(self):
        """Check if camera is initialized.

        Returns
        -------
        bool
            `True` if camera is initialized. Otherwise `False`.
        """
        return self._device.is_open()

    def is_acquiring(self):
        """Check if camera is acquiring images.

        Returns
        -------
        bool
            `True` if camera is acquiring images. Otherwise `False`.
        """
        return self._is_acquiring

    def initialize(self):
        """Initialize the camera.

        The function finds the XML description file (described in section
        4.1.2.1 of the GenICam GenTL Standard v1.5) of the camera and creates
        a node map based on it. After that it initializes a `features`
        dictionary containing the wrapped GenICam features.

        Raises
        ------
        RuntimeError
            If the URL pointing to XML description file is invalid.
        FileNotFoundError
            If GenICam XML description file is not found.
        """
        if not self.is_initialized():
            # Open device in such way, that only host has access to the device.
            # The process has read-and-write access to the device. This access
            # flag is described in section 6.4.3.1 of the GenICam GenTL
            # Standard (version 1.5).
            self._device.open(
                gtl.DEVICE_ACCESS_FLAGS_LIST.DEVICE_ACCESS_EXCLUSIVE
            )
            port = self._device.remote_port
            # Here we parse the URL, which tells the location of the XML
            # description file of the camera (there can be more than one). The
            # format of the URL is described in section 4.1.2.1 of the GenICam
            # GenTL Standard (version 1.5).
            xml_files = {}
            for url_info in port.url_info_list:
                splitted_url = url_info.url.split("?")
                if len(splitted_url) == 2:
                    others, schema_version = splitted_url
                else:
                    others = splitted_url
                location, others = others.split(":")
                if location == "local":
                    _, address, size = others.split(";")
                    xml_files["local"] = (int(address, 16), int(size, 16))
                elif location == "file":
                    splitted_url = others.split("///")
                    if len(splitted_url) == 2:
                        xml_files["file"] = splitted_url[1]
                    else:
                        xml_files["file"] = splitted_url
                elif location == "http":
                    xml_files["http"] = splitted_url
                else:
                    raise RuntimeError("Invalid URL.")

            if xml_files:  # Check that at least one XML file is found.
                # XML location preference:
                #   1. module register map
                if "local" in xml_files:
                    content = port.read(*xml_files["local"])[1]
                #   2. local directory
                elif "file" in xml_files:
                    with open(xml_files["file"], "r") as file:
                        content = file.read()
                #   3. vendor website
                elif "http" in xml_files:
                    with urllib.request.urlopen(xml_files["http"]) as file:
                        content = file.read()
            else:  # If no XML file is found, raise an exception.
                raise FileNotFoundError(
                        "No GenICam XML description file found.")

            # Create a BytesIO stream object using the `content` buffer.
            file_content = io.BytesIO(content)

            # According to GenICam GenTL Standard (v1.5, section 4.1.2) the XML
            # can be either an uncompressed XML description file or
            # Zip-compressed file (using DEFLATE and STORE compression methods).
            # Here we check if the file is a zip file, and extract the contents
            # if it is.
            if zipfile.is_zipfile(file_content):
                with zipfile.ZipFile(file_content, "r") as zip_file:
                    # Iterate over the files inside the zip.
                    for file in zip_file.infolist():
                        # Find the XML file using the file extension.
                        if os.path.splitext(file.filename)[1].lower() == ".xml":
                            content = zip_file.read(file).decode("utf8")

            _port = self._Port(port)

            self._node_map = gapi.NodeMap()  # Crate a node map
            # Load the XML description file contents to the node map.
            self._node_map.load_xml_from_string(content)
            # Connect the port to the node map instance.
            self._node_map.connect(_port, port.name)

            # Exclude features that are not implemented and wrap all the
            # remaining features inside feature objects, that simplify the usage
            # of the features.
            self._features = {}
            for feature_name in dir(self._node_map):  # Iterate over features.
                # Get feature from the node map.
                feature = getattr(self._node_map, feature_name)
                feature_type = type(feature)  # Get the `genicam2` type.
                # Exclude features that are not implemented (access mode `0`).
                if (feature_type in camazing.feature_types.mapping and
                        feature.get_access_mode() > 0):
                    # Select a proper wrapper type for feature and put it to
                    # features dictionary.
                    self._features[feature_name] = \
                        camazing.feature_types.mapping[feature_type](feature)

    def finalize(self):
        """Free the camera resources.

        Stops the acquisition if it's not already stopped. Also disconnect the
        node map and close the connection to the device.
        """
        # If acquisition is still running, stop acquisition.
        if self.is_acquiring():
            self.stop_acquisition()

        # If camera is initialized, free the resources.
        if self.is_initialized:
            if self._node_map is not None:
                self._node_map.disconnect()
                self._node_map = None
            self._device.close()

    @check_initialization
    def start_acquisition(self, n_buffers=None, payload_size=None, meta=None):
        """Start image acquisition.

        Parameters
        ----------
        n_buffers : int
            Number of buffers.
        payload_size : int
            Payload size.
        meta : list of str
            List of GenICam metadata fields to include in frames.
        """
        if not self.is_acquiring():

            # Initilize containers for buffers, events and data streams.
            self._buffers = {}
            self._events = []
            self._data_streams = []

            # Iterate over data stream IDs.
            for idx, stream_id in enumerate(self._device.data_stream_ids):

                # Create a data stream and open it.
                data_stream = self._device.create_data_stream()
                data_stream.open(stream_id)

                # An event object must be registered with `EVENT_NEW_BUFFER` in
                # order to be notified on newly filled buffers. See section
                # 5.2.4 of GenICam GenTL v1.5.
                event_token = data_stream.register_event(
                    gtl.EVENT_TYPE_LIST.EVENT_NEW_BUFFER
                )

                # Add the event to our container of events.
                self._events.append(gtl.EventManagerNewBuffer(event_token))

                # If payload size is not given as a parameter, see if it is
                # defined in the data stream or in the `PayloadSize` feature.
                if payload_size is None:
                    if data_stream.defines_payload_size():
                        payload_size = data_stream.payload_size
                    else:
                        payload_size = self["PayloadSize"].value

                # Create a container for all the buffer tokens.
                buffer_tokens = []

                # If the number of buffers is not given as a parameter, see
                # if the minimum number of buffers to be announced is defined
                # in the data stream.
                if n_buffers is None:
                    n_buffers = data_stream.buffer_announce_min

                for idx in range(n_buffers):
                    buffer = bytes(payload_size)
                    buffer_tokens.append(gtl.BufferToken(buffer, idx))

                # Create a container for the buffers.
                self._buffers[data_stream] = []

                # Announce buffers.
                for buffer_token in buffer_tokens:
                    self._buffers[data_stream].append(
                        data_stream.announce_buffer(buffer_token)
                    )

                # Start the acquisition engine, using the default behaviour.
                data_stream.start_acquisition(
                    gtl.ACQ_START_FLAGS_LIST.ACQ_START_FLAGS_DEFAULT
                )

                # Add the data stream to the list of available data streams.
                self._data_streams.append(data_stream)

                self["AcquisitionStart"].execute()
                self._is_acquiring = True

                # The pixel format doesn't change during image acquisition, so
                # we can save pixel format to attribute, and access it faster
                # later.
                self._pixel_format = self["PixelFormat"].value

                # Determine the decoder and range for the pixel format
                self._buffer_decoder = get_decoder(self._pixel_format)
                self._image_range = get_valid_range(self._pixel_format)

                # Keep some meta by default, if available
                self._meta = []
                for feature in ['Gain', 'ExposureTime', 'PixelFormat', 'PixelColorFilter']:
                    if feature in self._features:
                        self._meta.append(feature)

                self._frame_generator = self._get_frame_generator()

                # Not always implemented, even though this is defined as
                # mandatory by the GenICam standard. When acquisition is
                # ongoing, this prevents the adjusting of features critical
                # to the acquisition.
                if "TLParamsLocked" in self:
                    self["TLParamsLocked"].value = 1

    @check_initialization
    def stop_acquisition(self):
        """Stop image acquisition.

        Notes
        -----
        If acquisition has not been started, this function won't do anything.
        """
        # If acquisition is on, stop the acquisition. Otherwise do nothing.
        if self.is_acquiring():
            self["AcquisitionStop"].execute()

            # Not always implemented, even though this is defined as
            # mandatory by the GenICam standard. When acquisition is
            # ongoing, this prevents the adjusting of features critical
            # to the acquisition.
            if "TLParamsLocked" in self:
                self["TLParamsLocked"].value = 0

            # Flush the event queues and unregister the events.
            for event in self._events:
                event.flush_event_queue()
                event.unregister_event()

            # Clear the list of events.
            self._events.clear()

            # Iterate over available data streams.
            for data_stream in self._data_streams:

                # Stop the acquisition engine immediately. The Producer can
                # return a partially filled buffer through the regular
                # mechanism.
                data_stream.stop_acquisition(
                    gtl.ACQ_STOP_FLAGS_LIST.ACQ_STOP_FLAGS_KILL
                )

                # Discard all the buffers in the input pool and the buffers in
                # the output queue.
                data_stream.flush_buffer_queue(
                    gtl.ACQ_QUEUE_TYPE_LIST.ACQ_QUEUE_ALL_DISCARD
                )

                # Remove announced buffers from the acquisition engine.
                for buffer in self._buffers[data_stream]:
                    data_stream.revoke_buffer(buffer)

                data_stream.close()  # Finally close the data stream.

            # Clear the lists containing the buffers and data streams.
            self._buffers.clear()
            self._data_streams.clear()

            self._is_acquiring = False
            self._buffer_decoder = None
            self._image_range = None
            self._meta = None

    def _get_frame(self, timeout=1):
        """Helper function"""

        # Queue buffers
        for data_stream in self._data_streams:
            for buffer in self._buffers[data_stream]:
                data_stream.queue_buffer(buffer)

        buffer = None

        # Update the event data. There should be queued buffers available.
        for event in self._events:
            while buffer is None:
                if event.num_in_queue > 0:
                    event.update_event_data(timeout)
                    buffer = event.buffer

        # Check the payload type, and decide what to do with it. Payload types
        # are documented in section 6.4.4.5 in the version 1.5 of the GenICam
        # GenTL standard.
        # TODO: Build support for more
        # When the payload type is unknown, the data in it can be handled as
        # raw data.
        if (buffer.payload_type ==
                gtl.PAYLOADTYPE_INFO_IDS.PAYLOAD_TYPE_UNKNOWN):
            width = self["Width"].value
            height = self["Height"].value
        elif (buffer.payload_type ==
                gtl.PAYLOADTYPE_INFO_IDS.PAYLOAD_TYPE_IMAGE):
            width = buffer.width
            height = buffer.height
        else:
            raise Exception("Invalid payload type.")

        data = self._buffer_decoder(buffer.raw_buffer, (height, width))

        return data

    def _get_frame_with_meta(self):
        """Fetch a frame and add metadata from the camera."""

        data = self._get_frame()
        height, width = data.shape[0], data.shape[1]
        coords = {
            "x": ("x", np.arange(0, width) + 0.5),
            "y": ("y", np.arange(0, height) + 0.5),
            "timestamp": dt.datetime.today().timestamp(),
        }

        if 'RGB' in self._pixel_format:
            dims = ('y', 'x', 'colour')
            coords['colour'] = list('RGB')
        elif 'YUV' in self._pixel_format:
            dims = ('y', 'x', 'colour')
            coords['colour'] = list('YUV')
        elif 'YCbCr' in self._pixel_format:
            dims = ('y', 'x', 'colour')
            coords['colour'] = ['Y', 'Cb', 'Cr']
        else:
            dims = ('y', 'x')

        # Add metadata as coordinates
        if self._meta:
            coords.update({k: self._features[k].value for k in self._meta})

        frame = xr.DataArray(
            data,
            name="frame",
            dims=dims,
            coords=coords,
            attrs={
                'valid_range': self._image_range,
                }
        )

        return frame

    def _get_frame_generator(self):
        if self["TriggerMode"].value == "On" and self["TriggerSource"].value == "Software":
            while True:
                self["TriggerSoftware"].execute()
                yield self._get_frame_with_meta()
        else:
            self._get_frame_with_meta()
            while True:
                yield self._get_frame_with_meta()

    @check_initialization
    def get_frame(self):
        if not self.is_acquiring():
            raise AcquisitionException("Acquisition not started.")

        return next(self._frame_generator)

    def read_config_from_file(self, filepath=None):
        """Read configuration file and return it as a dict.

        The function assumes that the `filepath` given as a parameter contains
        a TOML configuration file (doesn't check the file extension) and starts
        parsing it. If no configuration file is passed as a parameter, the
        functions looks up the configuration from the default location, and
        evaluates the file if it finds one.

        Parameters
        ----------
        filepath : str or None, optional
            A file path to a TOML configuration file containing user given
            settings for the camera. If not given, will attempt to find
            a configuration from the default directory with the name
            "<Vendor>_<Model>_<Serial number>_<TL type>.toml"
            as given by the GenICam device info.

        Returns
        -------
        dict
            Dictionary of camera settings and their values.

        Raises
        ------
        FileNotFoundError
            If configuration file given as parameter is not found.
        TomlDecodeError
            If functions fails to parse the configuration file.

        Notes
        -----
        Since the set of features varies between camera models, configuration
        file is also model specific. However it's possible that same file can
        be used between two very similar camera models. Also, if the
        configuration file contains very few general settings, it's very
        likely that the file works with multiple cameras.
        """
        with open(filepath, "r") as file:
            settings = toml.load(file)  # Load the settings from a file.
        logger.info(f'Read list of settings from file `{filepath}`.')

        return settings

    def load_config_from_file(self, filepath):
        """Reads and immediately loads a config from a file.

        See `read_config_from_file` and `load_config_from_dict` for more info.

        Parameters
        ----------
        filepath : str
            A file path to a TOML configuration file containing user given
            settings for the camera.

        Returns
        -------
        unmodified settings : dict
            Subset of the original dictionary containing settings which could not
            be set even after iteration.
        reasons : dict
            Dictionary of unset feature names and reasons why they could not be set
            (in the final iteration).

        """
        return self.load_config_from_dict(
                self.read_config_from_file(filepath=filepath)
                )

    @check_initialization
    def load_config_from_dict(self, settings):
        """Load a given configuration from a dictionary.

        Attempt to set feature values based on a dictionary of
        feature names and values.

        Since settings may have interdependencies
        (setting A may set B to be write-only, for example), this process
        cannot be guaranteed to succeed even when the settings to be set
        have previously been dumped from the camera, when the settings are set
        in a unknown order. For this reason, the default behaviour is to loop
        through the given settings and attempt to set each value in order, until
        all the remaining settings are non-writable. Tries to get a value set are
        logged and can be seen by using a logger with level DEBUG.

        Parameters
        ----------
        settings : dict
            Dictionary of feature names and values.

        Returns
        -------
        unmodified settings : dict
            Subset of the original dictionary containing settings which could not
            be set even after iteration.
        reasons : dict
            Dictionary of unset feature names and reasons why they could not be set
            (in the final iteration).

        """
        # The following `while` loop probably needs some explanation. We cannot
        # just apply settings in the order they appear in the configuration
        # file. For example, if `Gain = 5` appears before `GainAuto = "Off"`,
        # we get in trouble. We can avoid this by skipping `Gain` and apply it
        # later. In the following `while` loop we only apply features that are
        # currently writable. When `GainAuto` is applied on first iteration,
        # we can apply `Gain` on the next iteration, etc.
        modified = True
        tries = dict(zip(settings.keys(), len(settings) * [0]))
        reasons = {}
        while modified:
            modified = False
            for feature in list(settings):
                tries[feature] = tries[feature] + 1
                logger.debug(f'Try {tries[feature]}: Setting feature `{feature}`')
                if "w" in self._features[feature].access_mode:
                    try:
                        self._features[feature].value = settings[feature]
                        settings.pop(feature)
                        modified = True
                    except ValueError as e:
                        reasons[feature] = e
                        logger.debug(
                            (f'Try {tries[feature]} of setting feature `{feature}` failed: '
                             f'{e}'))
                else:
                    reasons[feature] = 'Feature was not writable.'
                    logger.debug(
                        (f'Try {tries[feature]} of setting feature `{feature}` failed: '
                         f'feature access mode was `{self._features[feature].access_mode}`'))

        # Warning if there are any unloaded feature values.
        if settings:
            logger.warning(f'The following settings were not loaded due to errors:')
            for s, v in settings.items():
                logger.warning(f'{s}: {v}')
        logger.info('Finished setting feature values.')
        return settings, reasons

    @check_initialization
    def save_config_to_file(self, filepath, overwrite=False, **kwargs):
        """Save current camera configuration to a file.

        Tries to save all accessible camera features and their values to a
        file. By default only features that are set to read-write are included.
        If you want to include parameters that are read-only or write-only, pass
        access_modes=['r', 'w', 'rw'] or variants thereof. See `get_features`
        for other ways to select camera features.

        Parameters
        ----------
        filepath : str
            File to save the config to.

        overwrite : bool
            Whether to overwrite existing configuration file, if it exists.

        **kwargs
            Keyword arguments passed to get_features, used to select config
            features. By default only includes features with readable and 
            writable values.
        """
        def value(f):
            return f.value

        get_feature_args = dict(
            feature_types=camazing.feature_types.Valuable,
            access_modes=['rw'],
            )
        get_feature_args.update(kwargs)

        self._dump_features_to_file_with(
            value,
            filepath,
            overwrite,
            **get_feature_args,
            )

    @check_initialization
    def dump_feature_info(
            self,
            filepath,
            overwrite=False,
            **kwargs):
        """Dump all feature info from the camera to a configuration file.

        If no `filepath` is passed as a parameter, the functions tries to write
        the file to the default location. The existing file won't be
        overwritten unless the `overwrite` parameter is set to ``True``.

        Parameters
        ----------
        filepath : str or None, optional
            A file path where the file will be written.

        overwrite : bool
            True if one wishes to overwrite the existing file.

        **kwargs
            Keyword arguments for selecting features to dump using get_features.
        """
        def featureinfo(f):
            return f.info()

        self._dump_features_to_file_with(featureinfo, filepath, overwrite, **kwargs)

    @check_initialization
    def _dump_features_to_file_with(self, fun, filepath, overwrite=False, **kwargs):
        """Dump features into a file using a given function to pick out info.

        Parameters
        ----------
        fun : func
            Function to apply to each feature that extracts the info to be dumped.
            Must return a value serializable to toml.

        filepath : str
            File to dump the features to.

        overwrite : bool
            Whether to overwrite the given file if it already exists.
        """

        # If file exists with and `overwrite` parameter is not set to "
        # `True`, raise an exception.
        if os.path.isfile(filepath) and not overwrite:
            raise FileExistsError(
                "Cannot dump camera feature info to a file, because file "
                "`{}` already exists.".format(filepath) +
                "If you wan't to overwrite the existing file, set the "
                "`overwrite` parameter to `True`."
            )
            logger.error(f'Output file {filepath} already exists')

        features = {k: fun(v) for k, v in self.get_features(**kwargs).items()}

        with open(filepath, "w") as file:
            toml.dump(features, file)  # Dump the settings to a file.

        logger.info("Camera feature info dumped to `{}`".format(filepath))

    @check_initialization
    def get_features(
            self,
            feature_types=camazing.feature_types.Feature,
            access_modes=['', 'w', 'r', 'rw'],
            pattern='',
            ):
        """Return a filtered list of feature names.

        Parameters
        ----------
        feature_types : list
            List of feature types to include. See camazing.feature_types for
            valid values.

        access_modes : list of str
            Access modes to have in the result.

        pattern : str, optional
            Substring that must be included in the feature name.

        Returns
        -------
        features : dict
            Dictionary of feature names and corresponding feature objects.
        """
        settings = {}

        # Iterate over camera features and select only features which are
        # writable and which can be written (e.g. `Command` features don't have
        # a value).
        for feature_name, feature in self._features.items():
            if (isinstance(feature, feature_types) and
                    feature.access_mode in access_modes and
                    pattern in feature_name):
                settings[feature_name] = feature

        return settings
