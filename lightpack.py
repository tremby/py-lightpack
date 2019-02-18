from __future__ import print_function
from past.builtins import basestring

import re
import socket
from boltons import socketutils
from distutils.version import StrictVersion
try:
	from colour import Colour
except ImportError:
	Colour = None

NAME = 'py-lightpack'
DESCRIPTION = "Library to control Lightpack"
AUTHOR = "Bart Nagel" # And others including Mikhail Sannikov and René-Marc Simard
AUTHOR_EMAIL = 'bart@tremby.net'
URL = 'https://github.com/tremby/py-lightpack'
VERSION = '2.2.0'
LICENSE = "GNU GPLv3"

# Supported API version range
API_VERSION_GTE = StrictVersion('1.4')
API_VERSION_LTE = StrictVersion('2.2')

class Lightpack:
	"""
	Lightpack control class

	Most methods can raise a CommandFailedError if the command fails. The reason 
	could be an invalid parameter, lack of permissions, lock from another 
	process or something else, and this information will be in the exception.

	Commands that are not supported by your API version will raise either 
	CommandNotSupportedError or CommandDeprecatedError, depending on the case.

	Colours passed to the setColour, setColourToAll and setColours methods as 
	the `rgb` variable can be either a tuple of red, green and blue integers (in 
	the 0 to 255 range) or [Colour](https://github.com/tremby/py-colour) objects.
	"""

	def __init__(self, host='localhost', port=3636, led_map=None, api_key=None):
		"""
		Create a lightpack object.

		:param host: hostname or IP to connect to (default localhost)
		:type host: str
		:param port: port number to use (default 3636)
		:type port: int
		:param led_map: List of aliases for LEDs (default None -- no aliases)
		:type led_map: list
		:param api_key: API key (password) to provide (default None)
		:type api_key: str
		"""
		self.host = host
		self.port = port
		self.led_map = led_map
		self.api_key = api_key
		self.connection = None
		self._apiVersion = None
		self._countLeds = None
		self._countMonitors = None
		self._devices = []
		self._ledSizes = []
		self._maxLeds = None
		self._monitor = {}
		self._profiles = []
		self._screenSize = None

	def getApiVersion(self):
		"""
		Returns the detected API version.

		:returns: string response
		"""
		return str(self._apiVersion)

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
		data = self.connection.recv_until('\r\n'.encode('utf-8'))
		return data.decode('utf-8')

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

	def getColour(self, led):
		"""
		Get the specified LED's colour.

		:param led: 0-based LED index or its preconfigured alias
		:type led: str or int
		:returns: Tuple of red, green, blue values (0 to 255)
		"""
		return self.getColoursFromAll()[self._ledIndex(led)]
	getColor = getColour

	def getColours(self, *args):
		"""
		Get the individual colours of multiple LEDs.

		:returns: Dictionary of tuples of red, green, blue values (0 to 
		255), using LED numbers as integer keys
		"""
		defs = [self._ledIndex(arg) for arg in args]
		colours = self.getColoursFromAll()
		return dict([(k, colours[k]) for k in colours if k in defs])
	getColors = getColours

	def _ledColourRead(self, snippet):
		"""
		Read a LED colour state snippet into RGB Tuple.

		:param snippet: LED colour state snippet
		:type snippet: str
		:returns: Tuple with LED and tuple of red, green, blue values (0 to 
		255)
		"""
		led, colours = snippet.split('-', 1)
		rgb = [int(x) for x in colours.split(',', 2)]
		return int(led), tuple(rgb)

	def getColoursFromAll(self):
		"""
		Get the colours for all LEDs.

		:returns: Dictionary of tuples of red, green, blue values (0 to 
		255), using LED numbers as integer keys
		"""
		commands = self._sendAndReceivePayload('getcolors').rstrip(';')\
			.split(';')
		colours = {}
		for command in commands:
			data = self._ledColourRead(command)
			colours[data[0]] = data[1]
		return colours
	getColorsFromAll = getColoursFromAll

	def getColourAverage(self):
		"""
		Get the average colour of all LEDs.

		:returns: Tuple of red, green, blue values (0 to 255)
		"""
		try:
			r = g = b = 0
			colours = self.getColoursFromAll()
			for k in colours:
				r += colours[k][0]
				g += colours[k][1]
				b += colours[k][2]
			count = len(colours)
			return int(round(r / count)), int(round(g / count)), int(
					round(b / count))
		except ZeroDivisionError:
			return None
	getColorAverage = getColourAverage

	def getGamma(self):
		"""
		Get the current gamma correction value.

		Since API v1.5

		Raises a CommandNotSupportedError if API version is too low.

		:returns: float
		"""
		api_version_min = StrictVersion('1.5')
		if self._apiVersion < api_version_min:
			raise CommandNotSupportedError('getGamma()', api_version_min,
					self._apiVersion)
		return float(self._sendAndReceivePayload('getgamma'))

	def getSmoothness(self):
		"""
		Get the current smoothness value.

		Since API v1.5

		Raises a CommandNotSupportedError if API version is too low.

		:returns: integer
		"""
		api_version_min = StrictVersion('1.5')
		if self._apiVersion < api_version_min:
			raise CommandNotSupportedError('getSmoothness()', api_version_min,
					self._apiVersion)
		return int(self._sendAndReceivePayload('getsmooth'))

	def getBrightness(self):
		"""
		Get the current brightness value.

		Since API v1.5

		Raises a CommandNotSupportedError if API version is too low.

		:returns: integer
		"""
		api_version_min = StrictVersion('1.5')
		if self._apiVersion < api_version_min:
			raise CommandNotSupportedError('getBrightness()', api_version_min,
					self._apiVersion)
		return int(self._sendAndReceivePayload('getbrightness'))

	def getDevice(self):
		"""
		Get the current Lightpack device type.

		:returns: string
		"""
		return self._sendAndReceivePayload('getdevice')

	def getDevices(self, fresh=True):
		"""
		Get a list of compatible Lightpack device types.

		If the parameter fresh (default True) is set to False, a previously 
		cached value will be used if available.

		:param fresh: fetch a new value or use cached response
		:type fresh: boolean
		:returns: list of strings
		"""
		if fresh or self._devices == []:
			self._devices = self._sendAndReceivePayload('getdevices').rstrip(
				';').split(';')
		return self._devices

	def getFps(self):
		"""
		Get the current number of frames per second.

		:returns: integer
		"""
		return int(self._sendAndReceivePayload('getfps'))

	def getMode(self):
		"""
		Get the mode of the current profile.

		:returns: string
		"""
		return self._sendAndReceivePayload('getmode')

	def getPersistence(self):
		"""
		Get whether or not the last set colors should persist when unlocking.

		Since API v2.2

		Raises a CommandNotSupportedError if API version is too low.

		:returns: string, 'on', 'off', possibly others
		"""
		api_version_min = StrictVersion('2.2')
		if self._apiVersion < api_version_min:
			raise CommandNotSupportedError('getPersistence()', api_version_min,
					self._apiVersion)
		return self._sendAndReceivePayload('getpersistonunlock')

	def getProfiles(self, fresh=True):
		"""
		Get a list of profile names.

		If the parameter fresh (default True) is set to False, a previously 
		cached value will be used if available.

		:param fresh: fetch a new value or use cached response
		:type fresh: boolean
		:returns: list of strings
		"""
		if fresh or self._profiles == []:
			self._profiles = self._sendAndReceivePayload('getprofiles').rstrip(
				';').split(';')
		return self._profiles

	def getProfile(self):
		"""
		Get the name of the currently active profile.

		:returns: string
		"""
		return self._sendAndReceivePayload('getprofile')

	def getScreenSize(self, fresh=True):
		"""
		Get the dimensions of the screen.

		If the parameter fresh (default True) is set to False, a previously 
		cached value will be used if available.

		:param fresh: fetch a new value or use cached response
		:type fresh: boolean
		:returns: tuple of x-position, y-position, width and height
		"""
		if fresh or self._screenSize is None:
			try:
				coordinates = self._sendAndReceivePayload(
					'getscreensize').split(',', 3)
				rectangle = [int(x) for x in coordinates if x.strip()]
				self._screenSize = tuple(rectangle)
			except AttributeError:
				return None
			except ValueError:
				return None
		return self._screenSize

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

		:param fresh: fetch a new value or use cached response
		:type fresh: boolean
		:returns: integer
		"""
		if fresh or self._countLeds is None:
			self._countLeds = int(self._sendAndReceivePayload('getcountleds'))
		return self._countLeds

	def getMaxLeds(self, fresh=True):
		"""
		Get the maximum number of LEDs the Lightpack controls.

		If the parameter fresh (default True) is set to False, a previously 
		cached value will be used if available.

		:param fresh: fetch a new value or use cached response
		:type fresh: boolean
		:returns: integer
		"""
		if fresh or self._maxLeds is None:
			self._maxLeds = int(self._sendAndReceivePayload('getmaxleds'))
		return self._maxLeds

	def _ledSizeRead(self, command):
		"""
		Read a LED size state snippet into rectangle Tuple.

		:param command: LED size state snippet
		:type command: str
		:returns: Tuple with LED and tuple of x0, y0, x1, y1.
		"""
		led, coordinates = command.split('-', 1)
		rectangle = [int(x) for x in coordinates.split(',', 3)]
		return int(led), tuple(rectangle)

	def getLedSizes(self, fresh=True):
		"""
		Get the dimensions of all LEDs.

		If the parameter fresh (default True) is set to False, a previously 
		cached value will be used if available.

		:param fresh: fetch a new value or use cached response
		:type fresh: boolean
		:returns: Dictionary of tuples of x-position, y-position, height and
		width, using 0-based LED numbers as keys
		"""
		if fresh or self._ledSizes == {}:
			commands = self._sendAndReceivePayload('getleds').rstrip(';') \
				.split(';')
			self._ledSizes = {}
			for command in commands:
				data = self._ledSizeRead(command)
				self._ledSizes[data[0]] = data[1]
		return self._ledSizes

	def getSoundVizColours(self):
		"""
		Get min and max color for sound visualization mode.

		Since API v2.1

		Raises a CommandNotSupportedError if API version is too low.

		:returns: Tuple of two rgb tuples.
		"""
		api_version_min = StrictVersion('2.1')
		if self._apiVersion < api_version_min:
			raise CommandNotSupportedError('getSoundVizColours()', api_version_min,
					self._apiVersion)
		try:
			command = self._sendAndReceivePayload('getsoundvizcolors')
			parts = command.split(';', 1)
			colours = []
			for part in parts:
				rgb = part.split(',', 2)
				colours.append([int(x) for x in rgb if x.strip()])
			if len(colours) != 2:
				return None
		except ValueError:
			return None
		return tuple(colours[0]), tuple(colours[1])
	getSoundVizColors = getSoundVizColours

	def getSoundVizLiquid(self):
		"""
		Get whether or not sound visualization is in liquid color mode.

		Since API v2.1

		Raises a CommandNotSupportedError if API version is too low.

		:returns: string, 'ok' or 'no'.
		"""
		api_version_min = StrictVersion('2.1')
		if self._apiVersion < api_version_min:
			raise CommandNotSupportedError('getSoundVizLiquid()', api_version_min,
					self._apiVersion)
		return ('no', 'ok')[bool(self._sendAndReceivePayload(
			'getsoundvizliquid'))]

	def getCountMonitors(self, fresh=True):
		"""
		Get the number of monitors the Lightpack controls.

		If the parameter fresh (default True) is set to False, a previously 
		cached value will be used if available.

		:param fresh: fetch a new value or use cached response
		:type fresh: boolean
		:returns: integer
		"""
		if fresh or self._countMonitors is None:
			self._countMonitors = int(self._sendAndReceivePayload('countmonitors'))
		return self._countMonitors

	def getMonitorSize(self, monitor, fresh=True):
		"""
		Get the dimensions of a monitor.

		If the parameter fresh (default True) is set to False, a previously 
		cached value will be used if available.

		:param monitor: 0-based monitor index
		:type monitor: integer
		:param fresh: fetch a new value or use cached response
		:type fresh: boolean
		:returns: tuple of x-position, y-position, width and height
		"""
		if fresh or self._monitor == {} or monitor not in self._monitor:
			try:
				response = self._sendAndReceivePayload('getsizemonitor:%s' %
													   monitor)
				coordinates = response.split(',', 3)
				rectangle = [int(x) for x in coordinates if x.strip()]
				self._monitor[monitor] = tuple(rectangle)
			except AttributeError:
				return None
		return self._monitor[monitor]

	def getLockStatus(self):
		"""
		Get the API lock status (locked or unlocked).

		:returns: string, 'ok', 'no' or 'busy' depending on lock state.
		"""
		return self._sendAndReceivePayload('getlockstatus')

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
			connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			connection.connect((self.host, self.port))
			self.connection = socketutils.BufferedSocket(connection)
			greeting = self._readResult()
		except Exception as e:
			fail(e)

		# Check greeting and reported API version
		match = re.findall(r'API v?(\d+(?:\.\d+)?)', greeting)
		if match:
			match.sort(reverse=True)
			self._apiVersion = StrictVersion(match[0])
			if self._apiVersion < API_VERSION_GTE or self._apiVersion > \
					API_VERSION_LTE:
				fail("API version (%s) is not supported" % self._apiVersion)
		else:
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
		:type rgb: tuple
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
		:type rgb: tuple
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
		:type rgb: tuple
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

	def setDevice(self, device):
		"""
		Set the Lightpack device type.

		Deprecated in API v2.0

		:param device: device type (see `getDevices()`)
		:type device: str

		Raises a CommandDeprecatedError if no longer supported by API.
		"""
		api_version_max = StrictVersion('1.5')
		if self._apiVersion > api_version_max:
			raise CommandDeprecatedError('setDevice()', api_version_max,
					self._apiVersion)

		self._sendAndExpectOk('setdevice:%s' % device)

	def setMode(self, mode):
		"""
		Set the Lightpack mode.

		:param mode: mode to activate
		:type mode: str
		"""
		self._sendAndExpectOk('setmode:%s' % mode)

	def setProfile(self, profile):
		"""
		Set the current Lightpack profile.

		:param profile: profile to activate
		:type profile: str
		"""
		self._sendAndExpectOk('setprofile:%s' % profile)

	def addProfile(self, profile):
		"""
		Create a new Lightpack profile.

		:param profile: profile to create
		:type profile: str
		"""
		self._sendAndExpectOk('newprofile:%s' % profile)

	def deleteProfile(self, profile):
		"""
		Delete a Lightpack profile.

		:param profile: profile to delete
		:type profile: str
		"""
		self._sendAndExpectOk('deleteprofile:%s' % profile)

	def setCountLeds(self, count):
		"""
		Set the number of LEDs.

		Deprecated in API v2.0

		:param count: Number of LEDs
		:type count: int

		Raises a CommandDeprecatedError if no longer supported by API.
		"""
		api_version_max = StrictVersion('1.5')
		if self._apiVersion > api_version_max:
			raise CommandDeprecatedError('setCountLeds()', api_version_max,
					self._apiVersion)

		self._sendAndExpectOk('setcountleds:%s' % count)

	def _ledSizeDef(self, led, rectangle):
		"""
		Get the command snippet to set a particular LED to a particular size.

		:param led: 0-based LED index or its preconfigured alias
		:type led: str or int
		:param rectangle: Tuple of x-position, y-position, width and height
		"""
		return '%d-%d,%d,%d,%d' % tuple([self._ledIndex(led)] + list(
			rectangle))

	def setSize(self, led, rectangle):
		"""
		Set the specified LED to a specific position and size.

		:param led: 0-based LED index or its preconfigured alias
		:type led: str or int
		:param rectangle: x-position, y-position, width and height
		:type rectangle: tuple
		"""
		self._sendAndExpectOk('setleds:%s' % self._ledSizeDef(led, rectangle))

	def setSizes(self, *args):
		"""
		Set individual sizes of multiple LEDs.

		Each argument should be a tuple of (led, rectangle) for each LED to be 
		changed, where the elements of the tuples are the same as the arguments 
		for the `setSize` method.
		"""
		defs = [self._ledSizeDef(*arg) for arg in args]
		self._sendAndExpectOk('setleds:%s' % ';'.join(defs))

	def _colourDef(self, rgb):
		"""
		Get the command snippet to set a particular colour.

		:param rgb: Tuple of red, green, blue values (0 to 255) or Colour object
		:type rgb: tuple
		"""
		if Colour is not None and isinstance(rgb, Colour):
			rgb = rgb.rgb255()
		return '%d,%d,%d' % rgb

	def setSoundVizColour(self, min_rgb, max_rgb):
		"""
		Set min and max color for sound visualization.

		Since API v2.1

		:param min_rgb: Tuple of red, green, blue values (0 to 255) or 
		Colour object
		:type min_rgb: tuple
		:param max_rgb: Tuple of red, green, blue values (0 to 255) or 
		Colour object
		:type max_rgb: tuple

		Raises a CommandNotSupportedError if API version is too low.
		"""
		api_version_min = StrictVersion('2.1')
		if self._apiVersion < api_version_min:
			raise CommandNotSupportedError('setSoundVizColour()', api_version_min,
					self._apiVersion)
		self._sendAndExpectOk('setsoundvizcolors:%s;%s' % (self._colourDef(
			min_rgb), self._colourDef(max_rgb)))
	setSoundVizColor = setSoundVizColour

	def enableSoundVizLiquid(self):
		"""
		Set sound visualization to liquid color mode.

		Since API v2.1
		"""
		api_version_min = StrictVersion('2.1')
		if self._apiVersion < api_version_min:
			raise CommandNotSupportedError('setSoundVizLiquid()', api_version_min,
					self._apiVersion)
		self._sendAndExpectOk('setsoundvizliquid:on')

	def disableSoundVizLiquid(self):
		"""
		Disable sound visualization liquid color mode.

		Since API v2.1

		Raises a CommandNotSupportedError if API version is too low.
		"""
		api_version_min = StrictVersion('2.1')
		if self._apiVersion < api_version_min:
			raise CommandNotSupportedError('setSoundVizLiquid()', api_version_min,
					self._apiVersion)
		self._sendAndExpectOk('setsoundvizliquid:off')

	def setSession(self, key):
		"""
		Set the session key.

		:param key: session guid
		:type key: str
		"""
		self._sendAndExpectOk('guid:%s' % key)

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

	def persist(self):
		"""
		Set whether the last set colors should persist when unlocking.

		Since API v2.2

		:returns: string, 'ok', 'error', 'busy' or 'not locked', possibly 
		others

		Raises a CommandNotSupportedError if API version is too low.
		"""
		api_version_min = StrictVersion('2.2')
		if self._apiVersion < api_version_min:
			raise CommandNotSupportedError('enablePersistence()', api_version_min,
					self._apiVersion)
		return self._sendAndExpectOk('setpersistonunlock:on')

	def unpersist(self):
		"""
		Disable color persistence.

		Since API v2.2

		:returns: string, 'ok', 'error', 'busy' or 'not locked', possibly 
		others

		Raises a CommandNotSupportedError if API version is too low.
		"""
		api_version_min = StrictVersion('2.2')
		if self._apiVersion < api_version_min:
			raise CommandNotSupportedError('disablePersistence()', api_version_min, 
					self._apiVersion)
		return self._sendAndExpectOk('setpersistonunlock:off')

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


class CommandDeprecatedError(RuntimeError):
	def __init__(self, method, maximum, version):
		message = "%s is deprecated in API version '%s'. The last " \
				"compatible API version for this method is '%s'." \
				% (method, version, maximum)
		super(CommandDeprecatedError, self).__init__(message)
		self.method = method
		self.maximum = maximum
		self.version = version


class CommandNotSupportedError(RuntimeError):
	def __init__(self, method, minimum, version):
		message = "%s is not supported in API version '%s'. The minimum " \
				"required API version for this method is '%s'." \
				% (method, version, minimum)
		super(CommandNotSupportedError, self).__init__(message)
		self.method = method
		self.minimum = minimum
		self.version = version
