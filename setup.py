#!/usr/bin/env python

from distutils.core import setup
from setuptools import setup, find_packages

setup(
    name='django-classfield',
    version='1.0.6',
    description='Adds a class field to django',
    author='Mike Harris',
    url='https://github.com/mikeharris100/django-classfield',
    license='MIT',
    classifiers=[
        'License :: OSI Approved :: MIT License',
    ],
    packages=find_packages('.')
)
