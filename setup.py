#!/usr/bin/env python
# -*- coding: utf-8 -*-

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = [
    "appdirs",
    "genicam2",
    "netcdf4",
    "numpy",
    "tabulate",
    "toml",
    "xarray",
    "zipfile36"
]

setuptools.setup(
    name = "camazing",
    version = "0.1dev",
    description = "Machine vision library for GenICam-compliant cameras",
    long_description = long_description,
    long_description_content_type = "text/markdown",
    author = "Severi Jääskeläinen",
    author_email = "severij@tuta.io",
    url = "",
    packages = setuptools.find_packages(),
    licence = "MIT licence",
    install_requires = requirements,
    classifiers = (
        "Development Status :: 2 - Pre-Alpha",
        "Environment :: Console",
        "Intented Audience :: Developers",
        "Intented Audience :: Science/Research",
        "Licence :: OSI Approved :: MIT Licence",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
    )
)
