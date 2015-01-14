#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name='gEEProg',
    version='1.0',
    package_dir={'': 'src'},
    py_modules=['gEEProg'],
    install_requires=['pyserial'],
    author='Mark Chilenski',
    author_email='mark.chilenski@gmail.com',
    url='http://www.dasarodesigns.com/',
    description="GUI to control D'Asaro Designs EEPROM programmers.",
    long_description=open('README.rst', 'r').read(),
    license='GPL',
    scripts=['src/gEEProgGUI'],
    data_files=[('data/gEEProg', ['graphics/Icon.gif'])]
)