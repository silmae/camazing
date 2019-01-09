# camazing
Easy-to-use machine vision library for GenICam-compliant cameras

## Installation

### Prerequisites

camazing needs something called *GenTL Producer* in order to work. It enables
the library to access and configure the camera hardware in a generic way and
acquire images with the cameras. A more profound description can be found from
the GenICam GenTL standard. **Notice, that camazing currently works only when
there are exactly one GenTL Producer installed on the machine.** This is because
multiple paths to different GenTL Producers are listed in the
`GENICAM_GENTL64_PATH` environment variable, and camazing currently knows only
how to handle one.

The following implementations should not block cameras of competitive manufacturers:

| **Manufacturer** | **Software** | **Operating Systems** | **Status** |
| ------------------- | ------------------------ | --- | ----------------------- |
| [JAI](https://www.jai.com/) | [JAI SDK](https://www.jai.com/support-software/jai-software) | Windows | Not tested |
| [Matrix Vision](https://www.matrix-vision.com) | [mvIMPACT Acquire](http://static.matrix-vision.com/mvIMPACT_Acquire/) | Windows, Linux | Tested and working |
| [STEMMER IMAGING](https://www.stemmer-imaging.com/) | [Common Vision Blox](https://www.stemmer-imaging.com/en/products/category/common-vision-blox-the-machine-vision-operating-system/) | Windows, Linux (Ubuntu) | Not tested |

Also following software implement GenICam Producer, but they're likely to work
only with the cameras of the same manufacturer as the software:

| **Manufacturer** | **Software** | **Operating Systems** | **Status** |
| ---------------- | ------------ | --------------------- | ---------- |
|
| [Basler]() | [Pylon](https://www.baslerweb.com/en/products/software/basler-pylon-camera-software-suite/) | Windows, macOS, Linux | Tested, but camera driver missing |
| [Baumer Optotronic]() | [Baumer GAPI SDK](https://www.baumer.com/us/en/product-overview/image-processing-identification/software/baumer-gapi-sdk/c/14174) | Windows, Linux | Not tested |
| [OMRON SENTECH]() | [StCamUSBPack](https://sentech.co.jp/en/data/#cnt2nd) | ? | Not tested |

The installed software should define an environment variable
`GENICAM_GENTL64_PATH`, or `GENICAM_GENTL32_PATH` if you are using 32-bit CPU.
This contains the path to the GenICam Producer file with file extension `.cti`,
and camazing should be able to detect this automatically. If, however, the
environment variable is not defined for whatever reason, the GenICam Producer
can be provided to `CameraList` object manually.

## Installation using `pip`

TODO

## Usage

### Creating `CameraList` and `Camera`

First step is to get a list of available cameras. After importing camazing,
this can be achieved by creating a `CameraList` object:

```python
>>> import camazing
>>> cameras = camazing.CameraList()
```

`CameraList` is a singleton object, so no matter how many instances of the
class you try to create, they all will be refering to the same object. When new
cameras are connected to the machine, `CameraList` can be updated with method
`update()`. A quite nice representation of the `CameraList` can be outputted to
the console by simply typing in the variable `cameras` and hitting Enter:

```python
>>> cameras                                      
╒════╤═════════════════════╤═══════════════════════════╤═════════════════╤═══════════╕
│    │ Vendor              │ Model                     │   Serial number │ TL type   │
╞════╪═════════════════════╪═══════════════════════════╪═════════════════╪═══════════╡
│  0 │ Point Grey Research │ Grasshopper3 GS3-U3-91S6M │        17550532 │ U3V       │
├────┼─────────────────────┼───────────────────────────┼─────────────────┼───────────┤
│  1 │ Point Grey Research │ Grasshopper3 GS3-U3-23S6C │        15294589 │ U3V       │
╘════╧═════════════════════╧═══════════════════════════╧═════════════════╧═══════════╛
```

As we can see, we have two cameras connected to the system.

Let's say we then want to work with camera model GS3-U3-91S6M. First thing we
have to do is to get the camera from the list an initialize it:

```
>>> camera = cameras[0]
>>> camera.initialize()
```

As you can see, a specific camera can be accessed by using the corresponding
index number, which will be shown in the representation. After we've initialized
the camera, we can access the camera features and start the image acquisition.

## Features

### About GenICam SFNC

In order for the camera to be GenICam compliant, the features in the GenICam
XML must follow GenICam Standard Features Naming Convention. In addition to
naming convention, the document also provides a standard behavioral model for
the devices, so if you don't quite understand how some of the cameras features
work, it's good idea to check out that document. Documentation of camazing
won't provide any instructions how to use these features.

If worth noting that most of the features in the SFNC have level *recommended*
or *optional*, so don't be supprised if some specific feature is not
implemented in the camera. Camera manufacturers also might have features
implemented, that are not part of the GenICam SFNC.

### Accessing camera features

`Camera` is similar to Python dictionary object, *but not quite the same*.
Mainly, `Camera` object is immutable, meaning you cannot overwrite the features
in it. Also the object has method `features()` implemented instead of
`values()`. This is to avoid the confusion that `values()` would return the
actual values of features. `features()` returns a view of feature objects.
`Camera` has dictionary methods `items()` and `keys()`, as one would expect.
Using `keys()` you can get a listing of all implemented camera features:
```python
>>> camera.keys()
dict_keys(['AccessPrivilegeAvailable', 'AcquisitionFrameCount',
'AcquisitionFrameRate', 'AcquisitionFrameRateAuto',
'AcquisitionFrameRateEnabled', 'AcquisitionMode', 'AcquisitionStart',
'AcquisitionStatus', 'AcquisitionStatusSelector', 'AcquisitionStop',
'ActivePageNumber', 'ActivePageOffset', 'ActivePageSave', 'ActivePageValue',
'AutoExposureTimeLowerLimit', 'AutoExposureTimeUpperLimit',
'AutoFunctionAOIHeight', 'AutoFunctionAOIOffsetX', 'AutoFunctionAOIOffsetY',
'AutoFunctionAOIWidth', 'AutoFunctionAOIsControl', 'AutoGainLowerLimit',
'AutoGainUpperLimit', 'BalanceRatio', 'BalanceRatioSelector',
'BalanceWhiteAuto', 'BinningHorizontal', 'BinningVertical', 'BlackLevel',
'BlackLevelEnabled', 'ChunkBlackLevel', 'ChunkCRC', 'ChunkEnable',
'ChunkExposureTime', 'ChunkFrameCounter', 'ChunkGain', 'ChunkHeight',
'ChunkModeActive', 'ChunkOffsetX', 'ChunkOffsetY', 'ChunkPixelDynamicRangeMax',
'ChunkPixelDynamicRangeMin', 'ChunkPixelFormat', 'ChunkSelector',
'ChunkTimestamp', 'ChunkWidth', ...])
```
You can access a feature (in this example Gain) using the standard dictionary-like
syntax:
```python
>>> camera['Gain']
<camazing.util.Float object at 0x7f096686c7b8>
```
This is a `feature object` of type `Float`. The purpose of feature objects are
described in the next section. To get the value of gain, you can do it like so:
```python
>>> camera['Gain'].value
0
```
In this case Gain is 0 dB. If you want to change the value of Gain, you can do
it like this:
```python
camera['Gain'].value = 4
```
**Notice!** If you encounter `AccessModeException`, please check the Access mode
section of this tutorial.

### About feature objects and their methods

In camazing we have so called *feature objects*, that wrap the essential
functionality of the objects of the `genicam2` package. The point is to simplify
the usage, and provide more obvious function names. The following types of
feature objects are implemented:

* Boolean
* Enumeration
* Float
* Integer
* Command

Each feature object have the previously described `value` getter/setter. Each
object also have a `name` and a `description` getters, that can be used to
get a display name and a description of the feature (handy in case of UIs).
Some of these have more specialiced methods. For example `Enumeration` object has a
`valid_values` getter method, that can be used to list the values the particular
`Enumeration` object accepts.  Both `Integer` and `Float` objects have getter
methods `min` and `max`, that can be used to get the minimum and the maximum
value. In addition to this, `Integer` objects have a method called `increment`,
which can be used to ask the size of a minimal single increment (or decrement)
of value. Some `Float` objects also might have *a physical unit*, that can be
acquired with the `unit` getter.  `Command` is an action, that is executed with
the `execute()` method, and logically is *write-only*.

### Access mode

First thing to mention: Unlike in GenICam node map, where you can have a feature that have a
access mode of "Not implemented", camazing won't show those features in
the features listing. In camazing, access mode is represented using *readable*
and *writable* strings, `'r'` and `'w'`.

| `str`  | Meaning               |
| ------ | --------------------- |
| `''`   | Not available         |
| `'r'`  | Readable              |
| `'w'`  | Writable              |
| `'rw'` | Readable and writable |

Now, if you want to find out if Gain is writable, you can do it like this:
```python
>>> 'w' in camera['Gain'].access_mode
True
```

#### Why feature `X` is not available / read-only?

This is because some other feature is making it not available / read-only. For
example, Gain is `'rw'` only when value of GainAuto is `'Off'` or `'Once'`.
When value of GainAuto is `'Continuous'`, this mean that Gain will be
automatically adjusted and Gain itself will be read-only, or `'r'`.

Unfortunately, there is no way of turning features like GainAuto to `'Off'`
automatically when value is written to Gain. In principle this can be done, but
one would have to code that for each feature separately. That is a lot of
work, and unpredictable, since differemt cameras have a different set of features
implemented (including manufacturer specific, non-GenICam features).

## Image acquisition

There are many different ways to acquire images. One can use purely software to control the acquisition, or one can use user controlled hardware triggers. Different acquisition models might be covered here later, but for now (and for simplicity) we recommend using the following settings:
```python
camera['AcquisitionMode'].value = 'Continuous'
camera['TriggerMode'].value = 'On'
camera['TriggerSource'].value = 'Software'
```
These settings will ensure that you get complete frames when you call
`get_frame()`. This is the function that will give you single frame from the
camera when acquisition is ongoing. If acquisition is not started, this will
simply return an error. 

In order to capture images, the image acquisition has to be started. When you
are finished acquiring images, acquisition **must be stopped in order to free
the resources.**  The `Camera` object is a context manager, so the easiest and the
recommended way of doing this is to use the `with` keyword:
```python
>>> with camera:
...     camera.get_frame()
...
```
For sure there will be situations where this is not applicable.  An alternative
way to start the acquisition is to use `start_acquisition()` method, and finally
stop it with `stop_acquisition()`:

```python
>>> camera.start_acquisition()
>>> frame = camera.get_frame()
>>> camera.stop_acquisition()
```

### Using hardware trigger

When using hardware trigger, the only difference is that TriggerMode has to be
set to `'Hardware'` and TriggerSource has to be changed, like so:
```python
camera['TriggerMode'].value = 'Hardware'
camera['TriggerSource'].value = 'Line0'
```
TriggerSource depends on the camera and the trigger input used. Check the
manual of your specific camera model to check which trigger input you should
choose. When TriggerSource is set to use hardware trigger, the `get_frame()`
method will wait until hardware trigger is pressed, or when timeout is
exceeded. 

## Configuration (dumping and loading settings)

In the simplest case, you can dump the current settings of the camera to a
configuration file in OS specific default location with method 
```python
>>> camera.dump_config()
```
The location of configuration file will be determined by the [`appdirs`]()
package. If you don't know the default location in your OS, be sure to check the
documentation of the package, and especially the `user_config_dir` function.
camazing *won't overwrite existing files, unless the you
explicitly tells it to do so*. If you really want to overwrite an existing
configuration file, the `overwrite` parameter has to be set to `True`:
```python
>>> camera.dump_config(overwrite=True)
```
The configuration file can be loaded with the following method:
```python
>>> camera.load_config()
```
A config which was previously dumped to a file, and which is not manually modified after that, should be loaded without a hassle.
If any setting cannot be applied, camazing should raise a warning.

Of course, you're free to write your configuration files by hand. camazing uses
[TOML](https://github.com/toml-lang/toml) as its configuration language.  If
you're not familiar with it, do not worry. The
[specification](https://github.com/toml-lang/toml) of the language is relatively
short and the language is easy to learn.

### Why not use ...?

**INI**

* In Windows deprecated in favor of registry.
* No real specification (multiple different implementations).
* No support for Unicode.
* Contain only strings.
* Limited size (32KB).

**JSON**

* Noisy and not very readable.
* Doesn't support comments.
* Not designed to be a configuration language.

**YAML**

* Can be ambiguous.\* 
* Overly complex [spec](https://yaml.org/spec/1.2/spec.html).

\* For example, `'Off'` if interpreted as `True` in YAML. In case of camazing, this is a big issue, since many enumeration features can have value 'Off'.

**... multiple configuration languages?**

* Mainly to lessen the burden, and to keep things nice and neat.
* People have their own opinions about the right configuration language. If
  many configuration files will be written in different languages, it will be a
  mess.
* How to deal with files that have no file extension?

## Special thanks

The outcome of this project would not be possible without the efforts of
Kazunari Kudo @kazunarikudo, who wrote the GenICam Python bindings, and helped
us with the initial problems we faced when installing a GenTL Producer and
Harvester.