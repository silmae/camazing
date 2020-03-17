#!/usr/bin/env python
# -*- coding: utf-8 -*-

import setuptools

with open("README.md", "r", encoding='utf-8') as fh:
    long_description = fh.read()

requirements = [
    "genicam2",
    "numpy",
    "xarray",
    "toml",
    "tabulate",
    "zipfile36",
]

extras_requirements = {
    'docs': [
        'sphinx',
        'sphinxcontrib-napoleon',
        'sphinx-rtd-theme',
        'sphinx-markdown-tables',
        'recommonmark',
        ]
    }

setuptools.setup(
    name="camazing",
    version="0.9.0",
    description="Machine vision library for GenICam-compliant cameras",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Severi Jääskeläinen",
    author_email="severi.jaaskelainen@gmail.com",
    url="https://github.com/silmae/camazing",
    packages=setuptools.find_packages(),
    license="MIT licence",
    install_requires=requirements,
    extras_require=extras_requirements,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ]
)
