## Camera features

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


