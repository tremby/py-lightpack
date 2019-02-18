#!/usr/bin/env python

from setuptools import setup
import lightpack

with open('README.md', 'r') as fh:
	long_description = fh.read()

setup(name=lightpack.NAME,
		version=lightpack.VERSION,
		description=lightpack.DESCRIPTION,
		long_description=long_description,
		long_description_content_type='text/markdown',
		author=lightpack.AUTHOR,
		author_email=lightpack.AUTHOR_EMAIL,
		url=lightpack.URL,
		license=lightpack.LICENSE,
		py_modules=['lightpack']
		)
