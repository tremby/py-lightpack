import socket
import time
import imaplib
import re
import sys
try:
	from colour import Colour
except ImportError:
	Colour = None

NAME = 'py-lightpack'
DESCRIPTION = "Library to control Lightpack"
AUTHOR = "Bart Nagel <bart@tremby.net>, Mikhail Sannikov <atarity@gmail.com>"
URL = 'https://github.com/tremby/py-lightpack'
VERSION = '1.0.0'
LICENSE = "GNU GPLv3"

class lightpack:
	"""
	Lightpack control class

	Colours passed to the setColour, setColourToAll and setColours methods as 
	the `rgb` variable can be either a tuple of red, green and blue integers (in 
	the 0 to 255 range) or [Colour](https://github.com/tremby/py-colour) objects.
	"""

	def __init__(self, host='localhost', port=3636, \
			led_map=None, api_key = None):
		"""
		Create a lightpack object.

		:param host: hostname or IP to connect to (default localhost)
		:param port: port number to use (default 3636)
		:param led_map: List of aliases for LEDs (default None -- no aliases)
		:param api_key: API key (password) to provide (default None)
		"""
		self.host = host
		self.port = port
		self.led_map = led_map
		self.api_key = api_key
		self._countLeds = None

	def _ledIndex(self, led):
		"""
		Get the index of the given LED (by alias or index).

		:param led: 0-based LED index or its preconfigured alias
		:type led: str or int

		Raises an AliasDoesNotExistError if a given alias cannot be found.
		Raises an IndexError if an LED index is out of bounds.

		:returns: 1-based LED index
		"""
		if isinstance(led, basestring):
			try:
				return self.led_map.index(led) + 1
			except AttributeError:
				raise AliasDoesNotExistError("There are no aliases defined, " \
						"so can't resolve LED \"%s\"" % led)
			except ValueError:
				raise AliasDoesNotExistError("Alias \"%s\" isn't defined" % led)
		index = led + 1
		count = self.getCountLeds(fresh=False)
		if index > count:
			raise IndexError("LED (zero-)index %d out of range " \
					"(only %d LEDs are connected)" % (led, count))
		return index

	def _readResult(self):
		"""
		Return API response to most recent command.

		This is called in every local method.
		"""
		total_data = []
		data = self.connection.recv(8192)
		total_data.append(data)
		return ''.join(total_data).rstrip('\r\n')

	def _send(self, command):
		"""
		Send a command.

		:param command: command to send, without the trailing newline
		:type command: string
		"""
		self.connection.send(command + '\n')

	def _sendAndReceive(self, command):
		"""
		Send a command and get a response.

		:param command: command to send
		:type command: string
		:returns: string response
		"""
		self._send(command)
		return self._readResult()

	def getProfiles(self):
		"""
		Get a list of profile names.

		:returns: list of strings
		"""
		profiles = self._sendAndReceive('getprofiles')
		return profiles.split(':')[1].rstrip(';').split(';')

	def getProfile(self):
		"""
		Get the name of the currently active profile.

		:returns: string
		"""
		return self._sendAndReceive('getprofile').split(':')[1]

	def getStatus(self):
		"""
		Get the status of the Lightpack (on or off)

		:returns: string, 'on' or 'off'
		"""
		return self._sendAndReceive('getstatus').split(':')[1]

	def getCountLeds(self, fresh=True):
		"""
		Get the number of LEDs the Lightpack controls.

		If the parameter fresh (default True) is set to False, a previously 
		cached value will be used if available.

		:returns: integer
		"""
		if fresh or self._countLeds is None:
			self._countLeds = int( \
					self._sendAndReceive('getcountleds').split(':')[1])
		return self._countLeds

	def getAPIStatus(self):
		return self._sendAndReceive('getstatusapi').split(':')[1]

	def connect(self):
		"""
		Try to connect to the Lightpack API.

		A message is printed on failure.

		:returns: 0 on (probable) success, -1 on definite error
		"""
		try:
			self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.connection.connect((self.host, self.port))
			self._readResult()
			if self.api_key is not None:
				self._sendAndReceive('apikey:%s' % self.api_key)
			return 0
		except:
			print 'Lightpack API server is missing'
			return -1

	def _ledColourDef(self, led, rgb):
		"""
		Get the command snippet to set a particular LED to a particular colour.

		:param led: 0-based LED index or its preconfigured alias
		:type led: str or int
		:param rgb: Tuple of red, green, blue values (0 to 255) or Colour object
		"""
		if Colour is not None and isinstance(rgb, Colour):
			rgb = rgb.rgb255()
		return '%d-%d,%d,%d' % tuple([self._ledIndex(led)] + list(rgb))

	def setColour(self, led, rgb):
		"""
		Set the specified LED to the specified colour.

		:param led: 0-based LED index or its preconfigured alias
		:type led: str or int
		:param rgb: Tuple of red, green, blue values (0 to 255) or Colour object
		"""
		self._sendAndReceive('setcolor:%s' % self._ledColourDef(led, rgb))
	setColor = setColour

	def setColours(self, *args):
		"""
		Set individual colours of multiple LEDs.

		Each argument should be a tuple of (led, rgb) for each LED to be 
		changed, where the elements of the tuples are the same as the arguments 
		for the `setColour` method.
		"""
		defs = [self._ledColourDef(*arg) for arg in args]
		self._sendAndReceive('setcolor:%s' % ';'.join(defs))
	setColors = setColours

	def setColourToAll(self, rgb):
		"""
		Set all LEDs to the specified colour.

		:param rgb: Tuple of red, green, blue values (0 to 255) or Colour object
		"""
		defs = [self._ledColourDef(led, rgb) \
				for led in range(self.getCountLeds(fresh=False))]
		self._sendAndReceive('setcolor:%s' % ';'.join(defs))
	setColorToAll = setColourToAll

	def setGamma(self, gamma):
		self._sendAndReceive('setgamma:%s' % gamma)

	def setSmooth(self, smooth):
		self._sendAndReceive('setsmooth:%s' % smooth)

	def setBrightness(self, brightness):
		self._sendAndReceive('setbrightness:%s' % brightness)

	def setProfile(self, profile):
		"""
		Set the current Lightpack profile.

		:param profile: profile to activate
		:type profile: str
		"""
		self._sendAndReceive('setprofile:%s' % profile)

	def lock(self):
		"""
		Lock the Lightpack, thereby assuming control.

		While locked, the Lightpack's other functionality will be frozen. For 
		instance, it won't capture from the screen and update its colours while 
		locked.
		"""
		self._sendAndReceive('lock')

	def unlock(self):
		"""
		Unlock the Lightpack, thereby releasing control to other processes.
		"""
		self._sendAndReceive('unlock')

	def _setStatus(self, status):
		"""
		Set the status to a given string.

		:param status: status to set
		:type status: str
		"""
		self._sendAndReceive('setstatus:%s' % status)

	def turnOn(self):
		"""
		Turn the Lightpack on.
		"""
		self._setStatus('on')

	def turnOff(self):
		"""
		Turn the Lightpack off.
		"""
		self._setStatus('off')

	def disconnect(self):
		"""
		Unlock and disconnect from the Lightpack API.

		This method calls the `unlock()` method before disconnecting but will 
		not fail if the Lightpack is already unlocked.
		"""
		self.unlock()
		self.connection.close()

class AliasDoesNotExistError(RuntimeError):
	pass
