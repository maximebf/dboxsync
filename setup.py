#!/usr/bin/env python

from distutils.core import setup

setup(name='dboxsync',
      version='1.0',
      description='Syncs a Dropbox file or folder locally',
      author='Maxime Bouroumeau-Fuseau',
      author_email='maxime.bouroumeau@gmail.com',
      packages=['dboxsync'],
      scripts=['bin/dboxsync'],
      install_requires=['dropbox']
     )