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

Documentation
-------------

See the code or `pydoc lightpack` for full documentation.

Usage example
-------------

```python
import lightpack
from time import sleep
import sys

# Configuration
# host = 'localhost' # (default)
# port = 3636 # (default)
led_map = [ # Optional aliases for the LEDs in order
	'bottom-right',
	'right-bottom',
	'right-top',
	'top-far-right',
	'top-right',
	'top-left',
	'top-far-left',
	'left-top',
	'left-bottom',
	'bottom-left',
]
# api_key = '{secret-code}' # Default is None

# Connect to the Lightpack API
lp = lightpack.lightpack(led_map=led_map)
try:
	lp.connect()
except lightpack.CannotConnectError as e:
	print repr(e)
	sys.exit(1)

# Lock the Lightpack so we can make changes
lp.lock()

# Flash green three times
for i in range(3):
	# The American spellings such as setColorToAll are available as aliases
	lp.setColourToAll((0, 255, 0))
	sleep(0.2)
	lp.setColourToAll((0, 0, 0))
	sleep(0.2)

# Set top right light to yellow
# The Colour class is optional
from colour import Colour
lp.setColour('top-right', Colour('yellow'))

sleep(1)

# Set left bottom and left right lights to two other colours
lp.setColours(('left-bottom', Colour('red')), ('left-top', Colour('goldenrod')))

sleep(1)

# Unlock to release control (the disconnect method actually calls this 
# automatically, but it is often useful on its own so is here for informational 
# purposes)
lp.unlock()

# Disconnect
lp.disconnect()
```
