# Configuration (dumping and loading settings)

In the simplest case, you can dump the current settings of the camera to a
configuration file using
```python
>>> camera.save_config_to_file(<filename>)
```
Camazing *won't overwrite existing files, unless the you
explicitly tells it to do so*. If you really want to overwrite an existing
configuration file, the `overwrite` parameter has to be set to `True`:
```python
>>> camera.save_config_to_file(<filename>, overwrite=True)
```
The configuration file can be loaded with the following method:
```python
>>> not_applied, errors = camera.load_config_from_file(<filename>)
```
A config which was previously dumped to a file, and which is not manually modified after that, should be loaded without a hassle. The load function returns two dictionaries,
one containing the settings that could not be loaded to the camera, and the second
containing the associated exceptions with corresponding keys.

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


