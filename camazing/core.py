import atexit
import datetime as dt
import io
import logging
import os
import platform
import urllib
import sys
import warnings

import appdirs
import genicam2.gentl as gtl
import genicam2.genapi as gapi
import numpy as np
import tabulate
import toml
import xarray as xr

from camazing.util import Boolean, Enumeration, Integer, Float
from camazing.util import Singleton
from camazing.util import _types

# Some cameras are incompatible with zipfile package when Python version >= 3.7
if sys.version_info >= (3, 7):
    import zipfile36 as zipfile
else:
    import zipfile

# Define paths for configuration and log files. `appdirs` package gives us good
# defaults for different operating systems.
_config_dir = appdirs.user_config_dir("spectracular", False, None, False)
_log_dir = appdirs.user_log_dir("spectracular", False, None, False)

# If directory for configuration file doesn't exist, create it.
if not os.path.isdir(_config_dir):
    os.makedirs(_config_dir)

# If directory for log file doesn't exist, create it.
if not os.path.isdir(_log_dir):
    os.makedirs(_log_dir)

# Initialize the logger. By default the logging level will be `INFO`.
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
_formatter = logging.Formatter(
    "%(asctime)s  %>(levelname)s - %(message)s"
)
_file_handler = logging.FileHandler(os.path.join(_log_dir, "log"))
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(_formatter)
logger.addHandler(_file_handler)


class AcquisitionException(Exception):
    pass


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
    var = "GENICAM_GENTL64_PATH" if arch == "64bit" else "GENICAM_GENTL32_PATH"
    dir = os.getenv(var)  # Get the directory path in the environment variable.

    if dir:  # Check that the environment variable contains the directory path.
        for file in os.listdir(dir):
            # If `file` has extension `.cti`, we have found the CTI file.
            if file.endswith(".cti"):
                filepath = os.path.join(dir, file)
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
        "No GenICam Producer file (.cti) found from "
        "{} or {} environment variable.".format(filepath, var)
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


class Camera:

    class _Port(gapi.AbstractPort):

        def __init__(self, port):
            gapi.AbstractPort.__init__(self)
            self._port = port

        def read(self, address, size):
            buffer = self._port.read(address, size)
            return buffer[1]

        def write(self, address, value):
            self._port.write(address, value)

        def get_access_mode(self):
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
        return self.features[item]

    def __contains__(self, item):
        """Checks if `item` is in `features` dictionary.

        bool
            `True` if key is in the `features` dictionary. Otherwise `False`.
        """
        return item in self.features

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
                raise FileNotFoundError("No GenICam XML description file found.")

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
            # remaining features with wrappers, that simplify the usage of the
            # features.
            self.features = {}
            for feature_name in dir(self._node_map):  # Iterate over features.
                # Get feature from the node map.
                feature = getattr(self._node_map, feature_name)
                feature_type = type(feature)  # Get the `genicam2` type.
                # Exclude features that are not implemented (access mode `0`).
                if feature_type in _types and feature.get_access_mode() > 0:
                    # Select a proper wrapper type for feature and put it to
                    # features dictionary.
                    self.features[feature_name] = _types[feature_type](feature)

            # According to GenICam SFNC v2.4 `Gain` feature optional for camera
            # implementation. The following checks if `Gain` is implemented. If
            # `Gain` is implemented, it can be included in the `DataArray` when
            # picture is taken.
            self._has_gain = "Gain" in self

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

    def start_acquisition(self, n_buffers=None, payload_size=None):

        if not self.is_initialized:
            raise RuntimeError("Cannot start acquisition because the camera "
                               "is not initialized.")

        if not self.is_acquiring():

            self._buffers = {}
            self._events = []
            self._data_streams = []

            for idx, stream_id in enumerate(self._device.data_stream_ids):
                data_stream = self._device.create_data_stream()
                data_stream.open(stream_id)

                event_token = data_stream.register_event(
                    gtl.EVENT_TYPE_LIST.EVENT_NEW_BUFFER
                )

                self._events.append(gtl.EventManagerNewBuffer(event_token))

                if payload_size is None:
                    if data_stream.defines_payload_size():
                        payload_size = data_stream.payload_size
                    else:
                        payload_size = self["PayloadSize"].value

                buffer_tokens = []

                if n_buffers is None:
                    n_buffers = data_stream.buffer_announce_min

                for idx in range(n_buffers):
                    buffer = bytes(payload_size)
                    buffer_tokens.append(gtl.BufferToken(buffer, idx))

                self._buffers[data_stream] = []

                for buffer_token in buffer_tokens:
                    self._buffers[data_stream].append(
                        data_stream.announce_buffer(buffer_token)
                    )

                for buffer in self._buffers[data_stream]:
                    data_stream.queue_buffer(buffer)

                data_stream.start_acquisition(
                    gtl.ACQ_START_FLAGS_LIST.ACQ_START_FLAGS_DEFAULT
                )

                self._data_streams.append(data_stream)

                self["AcquisitionStart"].execute()
                self._is_acquiring = True

                self._pixel_format = self["PixelFormat"].value

                bits_per_pixel = int(self["PixelSize"].value.strip("Bpp"))

                # We need to define the datatype. E.g.
                if bits_per_pixel <= 8:
                    self._dtype = np.uint8
                elif bits_per_pixel <= 16:
                    self._dtype = np.uint16
                elif bits_per_pixel <= 32:
                    self._dtype = np.uint32
                elif bits_per_pixel <= 64:
                    self._dtype = np.uint64
                else:
                    raise Exception("Unsupported array data type.")

                self._frame_generator = self._get_frame_generator()

                # Not always implemented, even though this is defined as
                # mandatory by the GenICam standard.
                if "TLParamsLocked" in self:
                    self["TLParamsLocked"].value = 1

    def stop_acquisition(self):

        if self.is_acquiring():
            self["AcquisitionStop"].execute()

            if "TLParamsLocked" in self:
                self["TLParamsLocked"].value = 0

            for event in self._events:
                event.flush_event_queue()
                event.unregister_event()

            self._events.clear()

            for data_stream in self._data_streams:

                data_stream.stop_acquisition(
                    gtl.ACQ_STOP_FLAGS_LIST.ACQ_STOP_FLAGS_KILL
                )

                data_stream.flush_buffer_queue(
                    gtl.ACQ_QUEUE_TYPE_LIST.ACQ_QUEUE_ALL_DISCARD
                )

                for buffer in self._buffers[data_stream]:
                    data_stream.revoke_buffer(buffer)

                data_stream.close()

            self._buffers.clear()
            self._data_streams.clear()
            self._is_acquiring = False
            self._dtype = None

    def _get_frame(self, timeout=1):

        for data_stream in self._data_streams:
            for buffer in self._buffers[data_stream]:
                data_stream.queue_buffer(buffer)

        buffer = None

        for event in self._events:
            while buffer is None:
                if event.num_in_queue > 0:
                    event.update_event_data(timeout)
                    buffer = event.buffer

        if buffer.payload_type == gtl.PAYLOADTYPE_INFO_IDS.PAYLOAD_TYPE_UNKNOWN:
            width = self["Width"].value
            height = self["Height"].value
        elif buffer.payload_type == gtl.PAYLOADTYPE_INFO_IDS.PAYLOAD_TYPE_IMAGE:
            width = buffer.width
            height = buffer.height
        else:
            raise Exception("Invalid payload type.")

        data = np.frombuffer(
            buffer.raw_buffer,
            self._dtype
        ).reshape(height, width).copy()

        coords = {
            "x": ("x", np.arange(0, width)),
            "y": ("y", np.arange(0, height)),
            "timestamp": dt.datetime.today().timestamp(),
            "exposure_time": self["ExposureTime"].value
        }

        if self._has_gain:
            coords["gain"] = self["Gain"].value

        frame = xr.DataArray(
            data,
            name="frame",
            dims=["y", "x"],
            coords=coords,
            attrs={"pixel_format": self._pixel_format}
        )

        return frame

    def _get_frame_generator(self):
        if self["TriggerMode"].value == "On" and self["TriggerSource"].value == "Software":
            while True:
                self["TriggerSoftware"].execute()
                yield self._get_frame()
        else:
            self._get_frame()
            while True:
                yield self._get_frame()

    def get_frame(self):
        if not self.is_acquiring():
            raise AcquisitionException("Acquisition not started.")

        return next(self._frame_generator)

    def load_config(self, filepath=None):
        """Load configuration file and apply all the settings written in the
        file to the camera.

        The function assumes that the `filepath` given as a parameter contains
        a TOML configuration file (doesn't check the file extension) and starts
        parsing it. If no configuration file is passed as a parameter, the
        functions looks up the configuration from the default location, and
        evaluates the file if it finds one.

        Parameters
        ----------
        filepath : str or None
            A file path to a TOML configuration file containing user given
            settings for the camera.

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
        # If `filepath` is None, load the configuration file from the default
        # location.
        if filepath is None:
            filepath = os.path.join(_config_dir, "camera.toml")

        with open(filepath, "r") as file:
            settings = toml.load(file)  # Load the settings from a file.

        # The following `while` loop probably needs some explanation. We cannot
        # just apply settings in the order they appear in the configuration
        # file. For example, if `Gain = 5` appears before `GainAuto = "Off"`,
        # we get in trouble. We can avoid this by skipping `Gain` and apply it
        # later. In the following `while` loop we only apply features that are
        # currently writable. When `GainAuto` is applied on first iteration,
        # we can apply `Gain` on the next iteration, etc.
        modified = True
        while modified:
            modified = False
            for feature in list(settings):
                if "w" in self.features[feature].access_mode:
                    self.features[feature].value = settings[feature]
                    settings.pop(feature)
                    modified = True

        # Warning if there are any unloaded feature values.
        if settings:
            warnings.warn(
                f"Couldn't load the values of the following "
                f"features:\n\n{settings}\n\nThese features don't seem to be "
                "writable after loading all the other settings.")

    def dump_config(self, filepath=None, overwrite=False):
        """Dump the current settings of the camera to a configuration file.

        If no `filepath` is passed as a parameter, the functions tries to write
        the file to the default location. The existing file won't be
        overwritten unless the `overwrite` parameter is set to ``True``.

        Parameters
        ----------
        filepath : str or None
            A file path where the configuration file will be written. If
            ``None``, the file will be written to the default location.
        overwrite : bool
            True if one wishes to overwrite the existing file.
        """
        # If `filepath` is None, dump the configuration file to the default
        # location.
        if filepath is None:
            filepath = _config_dir + "/camera.toml"

        # If file exists with and `overwrite` parameter is not set to "
        # `True`, raise an exception.
        if os.path.isfile(filepath) and not overwrite:
            raise FileExistsError(
                "Cannot dump camera settings to a file, because file "
                "`{}` already exists.".format(filepath) +
                "If you wan't to overwrite the existing file, set the "
                "`overwrite` parameter to `True`."
            )

        settings = {}

        # Iterate over camera features and select only features which are
        # writable and which can be written (e.g. `Command` features don't have
        # a value).
        valid_types = (Boolean, Enumeration, Float, Integer)
        for feature_name, feature in self.features.items():
            if type(feature) in valid_types and "w" in feature.access_mode:
                settings[feature_name] = feature.value

        with open(filepath, "w") as file:
            toml.dump(settings, file)  # Dump the settings to a file.

        logger.info("Camera configuration dumped to `{}`".format(filepath))
