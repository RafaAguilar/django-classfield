#!/usr/bin/env python

from distutils.core import setup
from setuptools import setup, find_packages

setup(
    name='django-classfield',
    version='1.0.7',
    description='Adds a class field to django',
    author='Mike Harris, Mike Amy',
    author_email='michael.amy@wfp.org',
    url='https://github.com/MikeAmy/django-classfield',
    license='MIT',
    classifiers=[
        'License :: OSI Approved :: MIT License',
    ],
    packages=find_packages('.')
)
