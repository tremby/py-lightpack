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

	def __init__(self, host, port, ledMap, apikey = None):
		"""
		Create a lightpack object.

		:param host: hostname or IP to connect to
		:param port: port number to use
		:param ledMap: List of aliases for LEDs
		:param apikey: API key (password) to provide
		"""
		self.host = host
		self.port = port
		self.ledMap = ledMap
		self.apikey = apikey

	def __ledIndex(self, led):
		"""
		Get the index of the given LED (by alias or index).

		:param led: 0-based LED index or its preconfigured alias
		:type led: str or int

		:returns: 1-based LED index
		"""
		if isinstance(led, basestring):
			return self.ledMap.index(led) + 1
		return led + 1

	def __readResult(self):
		"""
		Return API response to most recent command.

		This is called in every local method.
		"""
		total_data = []
		data = self.connection.recv(8192)
		total_data.append(data)
		return ''.join(total_data).rstrip('\r\n')

	def __send(self, command):
		"""
		Send a command.

		:param command: command to send, without the trailing newline
		:type command: string
		"""
		self.connection.send(command + '\n')

	def __sendAndReceive(self, command):
		"""
		Send a command and get a response.

		:param command: command to send
		:type command: string
		:returns: string response
		"""
		self.__send(command)
		return self.__readResult()

	def getProfiles(self):
		"""
		Get a list of profile names.

		:returns: list of strings
		"""
		profiles = self.__sendAndReceive('getprofiles')
		return profiles.split(':')[1].rstrip(';').split(';')

	def getProfile(self):
		"""
		Get the name of the currently active profile.

		:returns: string
		"""
		return self.__sendAndReceive('getprofile').split(':')[1]

	def getStatus(self):
		"""
		Get the status of the Lightpack (on or off)

		:returns: string, 'on' or 'off'
		"""
		return self.__sendAndReceive('getstatus').split(':')[1]

	def getCountLeds(self):
		"""
		Get the number of LEDs the Lightpack controls.

		:returns: integer
		"""
		return int(self.__sendAndReceive('getcountleds').split(':')[1])

	def getAPIStatus(self):
		return self.__sendAndReceive('getstatusapi').split(':')[1]

	def connect(self):
		"""
		Try to connect to the Lightpack API.

		A message is printed on failure.

		:returns: 0 on (probable) success, -1 on definite error
		"""
		try:
			self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.connection.connect((self.host, self.port))
			self.__readResult()
			if self.apikey is not None:
				self.__sendAndReceive('apikey:%s' % self.apikey)
			return 0
		except:
			print 'Lightpack API server is missing'
			return -1

	def __ledColourDef(self, led, rgb):
		"""
		Get the command snippet to set a particular LED to a particular colour.

		:param led: 0-based LED index or its preconfigured alias
		:type led: str or int
		:param rgb: Tuple of red, green, blue values (0 to 255) or Colour object
		"""
		if Colour is not None and isinstance(rgb, Colour):
			rgb = rgb.rgb255()
		return '%d-%d,%d,%d' % tuple([self.__ledIndex(led)] + list(rgb))

	def setColour(self, led, rgb):
		"""
		Set the specified LED to the specified colour.

		:param led: 0-based LED index or its preconfigured alias
		:type led: str or int
		:param rgb: Tuple of red, green, blue values (0 to 255) or Colour object
		"""
		self.__sendAndReceive('setcolor:%s' % self.__ledColourDef(led, rgb))
	setColor = setColour

	def setColours(self, *args):
		"""
		Set individual colours of multiple LEDs.

		Each argument should be a tuple of (led, rgb) for each LED to be 
		changed, where the elements of the tuples are the same as the arguments 
		for the `setColour` method.
		"""
		defs = [self.__ledColourDef(*arg) for arg in args]
		self.__sendAndReceive('setcolor:%s' % ';'.join(defs))
	setColors = setColours

	def setColourToAll(self, rgb):
		"""
		Set all LEDs to the specified colour.

		:param rgb: Tuple of red, green, blue values (0 to 255) or Colour object
		"""
		defs = [self.__ledColourDef(led, rgb) \
				for (led, _) in enumerate(self.ledMap)]
		self.__sendAndReceive('setcolor:%s' % ';'.join(defs))
	setColorToAll = setColourToAll

	def setGamma(self, gamma):
		self.__sendAndReceive('setgamma:%s' % gamma)

	def setSmooth(self, smooth):
		self.__sendAndReceive('setsmooth:%s' % smooth)

	def setBrightness(self, brightness):
		self.__sendAndReceive('setbrightness:%s' % brightness)

	def setProfile(self, profile):
		"""
		Set the current Lightpack profile.

		:param profile: profile to activate
		:type profile: str
		"""
		self.__sendAndReceive('setprofile:%s' % profile)

	def lock(self):
		"""
		Lock the Lightpack, thereby assuming control.

		While locked, the Lightpack's other functionality will be frozen. For 
		instance, it won't capture from the screen and update its colours while 
		locked.
		"""
		self.__sendAndReceive('lock')

	def unlock(self):
		"""
		Unlock the Lightpack, thereby releasing control to other processes.
		"""
		self.__sendAndReceive('unlock')

	def __setStatus(self, status):
		"""
		Set the status to a given string.

		:param status: status to set
		:type status: str
		"""
		self.__sendAndReceive('setstatus:%s' % status)

	def turnOn(self):
		"""
		Turn the Lightpack on.
		"""
		self.__setStatus('on')

	def turnOff(self):
		"""
		Turn the Lightpack off.
		"""
		self.__setStatus('off')

	def disconnect(self):
		"""
		Unlock and disconnect from the Lightpack API.

		This method calls the `unlock()` method before disconnecting but will 
		not fail if the Lightpack is already unlocked.
		"""
		self.unlock()
		self.connection.close()
