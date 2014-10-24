py-lightpack
============

This is a Python library for controlling [Lightpack](http://lightpack.tv/)

It is a fork of [the official Python library](https://github.com/Atarity/Lightpack/blob/master/Software/apiexamples/pyLightpack/lightpack.py), which at the time of writing is buggy, unpackaged, unmaintained and undocumented.
The goal of this project is to address those issues and make other improvements.

Installation
------------

Install from PiPI:

	sudo pip install py-lightpack

Or install from source by cloning this repository and running

	sudo python setup.py install

Usage example
-------------

```python
import lightpack
from time import sleep

# Configuration
host = 'localhost'
port = 3636
api_key = 'my-api-key'
light_map = [i + 1 for i in range(10)]

# Connect to the Lightpack
lp = lightpack.lightpack(host, port, light_map, api_key)
lp.connect()

# Lock the Lightpack so we can make changes
lp.lock()

# Flash green three times
for i in range(3):
	lp.setColorToAll(0, 255, 0)
	sleep(0.2)
	lp.setColorToAll(0, 0, 0)
	sleep(0.2)

# Unlock to release control
lp.unlock()
```
