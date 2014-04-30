#!/usr/bin/env python

from setuptools import setup

setup(name='dboxsync',
      version='0.1',
      description='Syncs a Dropbox file or folder locally',
      author='Maxime Bouroumeau-Fuseau',
      author_email='maxime.bouroumeau@gmail.com',
      packages=['dboxsync'],
      scripts=['bin/dboxsync'],
      install_requires=['dropbox']
     )