# Usage

## Creating `CameraList` and `Camera`

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


