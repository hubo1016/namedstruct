#!/usr/bin/env python
'''
Created on 2015/11/17

:author: hubo
'''
try:
    import ez_setup
    ez_setup.use_setuptools()
except:
    pass
from setuptools import setup, find_packages

VERSION = '1.2.1'

setup(name='nstruct',
      version=VERSION,
      description='Define complicate C/C++ structs in Python to parse/pack them from/to raw bytes',
      author='Hu Bo',
      author_email='hubo1016@126.com',
      license="http://www.apache.org/licenses/LICENSE-2.0",
      url='http://github.com/hubo1016/namedstruct',
      keywords=['Openflow', 'struct', 'parse', 'protocol'],
      test_suite = 'tests',
      use_2to3=False,
      install_requires = [],
      packages=find_packages(exclude=("tests","tests.*","misc","misc.*")))
