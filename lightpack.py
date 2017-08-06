from __future__ import print_function
from past.builtins import basestring

import socket
import time
import imaplib
import re
import sys
from distutils.version import StrictVersion
try:
	from colour import Colour
except ImportError:
	Colour = None

NAME = 'py-lightpack'
DESCRIPTION = "Library to control Lightpack"
AUTHOR = "Bart Nagel <bart@tremby.net>, Mikhail Sannikov <atarity@gmail.com>"
URL = 'https://github.com/tremby/py-lightpack'
VERSION = '2.1.0'
LICENSE = "GNU GPLv3"

# Supported API version range
API_VERSION_GTE = StrictVersion('1.4')
API_VERSION_LTE = StrictVersion('1.5')

class Lightpack:
	"""
	Lightpack control class

	Most methods can raise a CommandFailedError if the command fails. The reason 
	could be an invalid parameter, lack of permissions, lock from another 
	process or something else, and this information will be in the exception.

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
		data = self.connection.recv(8192)
		return data.decode('utf-8').rstrip('\r\n')

	def _commandPart(self, string, part):
		"""
		Get one part of a command or response -- the name or the payload.
		"""
		try:
			return string.split(':', 1)[part]
		except IndexError:
			return None

	def _name(self, string):
		"""
		Get the command name part of a command or response (the part before the 
		first colon).
		"""
		return self._commandPart(string, 0)

	def _payload(self, string):
		"""
		Get the payload part of a command or response (the part after the first 
		colon).
		"""
		return self._commandPart(string, 1)

	def _send(self, command):
		"""
		Send a command.

		:param command: command to send, without the trailing newline
		:type command: str
		"""
		self.connection.send(str.encode(command + '\n'))

	def _sendAndReceive(self, command):
		"""
		Send a command and get a response.

		:param command: command to send
		:type command: str
		:returns: string response
		"""
		self._send(command)
		return self._readResult()

	def _sendAndReceivePayload(self, command):
		"""
		Send a command and get the payload.

		:param command: command to send
		:type command: str
		:returns: string payload
		"""
		return self._payload(self._sendAndReceive(command))

	def _sendAndExpect(self, command, expected_response):
		"""
		Send a command and raise a CommandFailedError if a particular response 
		is not received.

		:param command: command to send
		:type command: str
		:param expected_response: expected response
		:type expected_response: str
		"""
		response = self._sendAndReceive(command)
		if response == expected_response:
			return
		raise CommandFailedError(command, response, expected_response)

	def _sendAndExpectOk(self, command):
		"""
		Send a command and raise a CommandFailedError if 'ok' is not received.

		:param command: command to send
		:type command: str
		"""
		self._sendAndExpect(command, 'ok')

	def _sendAndExpectSuccess(self, command):
		"""
		Send a command and raise a CommandFailedError if 'commandname:success' 
		is not received.

		:param command: command to send
		:type command: str
		"""
		self._sendAndExpect(command, '%s:success' % self._name(command))

	def getProfiles(self):
		"""
		Get a list of profile names.

		:returns: list of strings
		"""
		return self._sendAndReceivePayload('getprofiles').rstrip(';').split(';')

	def getProfile(self):
		"""
		Get the name of the currently active profile.

		:returns: string
		"""
		return self._sendAndReceivePayload('getprofile')

	def getStatus(self):
		"""
		Get the status of the Lightpack (on or off, or possibly other status).

		:returns: string, 'on', 'off' or 'unknown', possibly others
		"""
		return self._sendAndReceivePayload('getstatus')

	def getCountLeds(self, fresh=True):
		"""
		Get the number of LEDs the Lightpack controls.

		If the parameter fresh (default True) is set to False, a previously 
		cached value will be used if available.

		:returns: integer
		"""
		if fresh or self._countLeds is None:
			self._countLeds = int(self._sendAndReceivePayload('getcountleds'))
		return self._countLeds

	def getApiStatus(self):
		"""
		Get the API status (busy or idle).

		:returns: string, 'busy' or 'idle' depending on lock state.
		"""
		return self._sendAndReceivePayload('getstatusapi')

	def connect(self):
		"""
		Connect to the Lightpack API.

		A CannotConnectError is raised on failure.
		"""

		# Function to run if we fail
		def fail(cause = None):
			raise CannotConnectError("Could not connect to %s:%d (%s an API key)" % ( \
					self.host, \
					self.port, \
					"without" if self.api_key is None else "with"), \
					cause)

		# Attempt to connect
		try:
			self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.connection.connect((self.host, self.port))
			greeting = self._readResult()
		except Exception as e:
			fail(e)

		# Check greeting and reported API version
		match = re.match(r'^Lightpack API v(\S+)', greeting)
		version = StrictVersion(match.group(1))
		if version < API_VERSION_GTE or version > API_VERSION_LTE:
			fail("API version (%s) is not supported" % version)
		if not match:
			print(match)
			fail("Unrecognized greeting from server: \"%s\"" % greeting)

		# Give API key if we have one
		if self.api_key is not None:
			response = self._sendAndReceive('apikey:%s' % self.api_key)
			if response != 'ok':
				fail("bad API key (server responded '%s')" % response)

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
		self._sendAndExpectOk('setcolor:%s' % self._ledColourDef(led, rgb))
	setColor = setColour

	def setColours(self, *args):
		"""
		Set individual colours of multiple LEDs.

		Each argument should be a tuple of (led, rgb) for each LED to be 
		changed, where the elements of the tuples are the same as the arguments 
		for the `setColour` method.
		"""
		defs = [self._ledColourDef(*arg) for arg in args]
		self._sendAndExpectOk('setcolor:%s' % ';'.join(defs))
	setColors = setColours

	def setColourToAll(self, rgb):
		"""
		Set all LEDs to the specified colour.

		:param rgb: Tuple of red, green, blue values (0 to 255) or Colour object
		"""
		defs = [self._ledColourDef(led, rgb) \
				for led in range(self.getCountLeds(fresh=False))]
		self._sendAndExpectOk('setcolor:%s' % ';'.join(defs))
	setColorToAll = setColourToAll

	def setGamma(self, gamma):
		"""
		Set the gamma setting to the given value.

		:param gamma: gamma in the range 0.01 to 10.0
		:type gamma: float
		"""
		self._sendAndExpectOk('setgamma:%s' % gamma)

	def setSmoothness(self, smoothness):
		"""
		Set the smoothness setting to the given value.

		With a smoothness of 0 the colours change suddenly. With a positive 
		smoothness the colours gradually change.

		:param smoothness: smoothness in the range 0 to 255
		:type smoothness: int
		"""
		self._sendAndExpectOk('setsmooth:%s' % smoothness)

	def setBrightness(self, brightness):
		"""
		Set the brightness modifier of all LEDs to the given value.

		:param brightness: brightness in the range 0 to 100
		:type brightness: int
		"""
		self._sendAndExpectOk('setbrightness:%s' % brightness)

	def setProfile(self, profile):
		"""
		Set the current Lightpack profile.

		:param profile: profile to activate
		:type profile: str
		"""
		self._sendAndExpectOk('setprofile:%s' % profile)

	def lock(self):
		"""
		Lock the Lightpack, thereby assuming control.

		While locked, the Lightpack's other functionality will be frozen. For 
		instance, it won't capture from the screen and update its colours while 
		locked.
		"""
		self._sendAndExpectSuccess('lock')

	def unlock(self):
		"""
		Unlock the Lightpack, thereby releasing control to other processes.
		"""
		self._sendAndExpectSuccess('unlock')

	def _setStatus(self, status):
		"""
		Set the status to a given string.

		:param status: status to set
		:type status: str
		"""
		self._sendAndExpectOk('setstatus:%s' % status)

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
		try:
			self.unlock()
		except CommandFailedError:
			pass
		self.connection.close()

class CannotConnectError(RuntimeError):
	def __init__(self, message, cause = None):
		if cause is not None:
			message += ", caused by %s" % \
					(cause if isinstance(cause, basestring) else repr(cause))
		super(CannotConnectError, self).__init__(message)
		self.cause = cause
class NotAuthorizedError(RuntimeError):
	pass
class AliasDoesNotExistError(RuntimeError):
	pass
class CommandFailedError(RuntimeError):
	def __init__(self, command, response, expected):
		super(CommandFailedError, self).__init__( \
				"Command \"%s\" failed; response \"%s\", expected \"%s\"" % \
				(command, response, expected))
		self.command = command
		self.response = response
		self.expected = expected
