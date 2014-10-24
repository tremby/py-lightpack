import socket
import time
import imaplib
import re
import sys

NAME = 'py-lightpack'
DESCRIPTION = "Library to control Lightpack"
AUTHOR = "Bart Nagel <bart@tremby.net>, Mikhail Sannikov <atarity@gmail.com>"
URL = 'https://github.com/tremby/py-lightpack'
VERSION = '1.0.0'
LICENSE = "GNU GPLv3"

class lightpack:
	"""
	Lightpack control class
	"""

	def __init__(self, _host, _port, _ledMap, _apikey = None):
		"""
		Create a lightpack object.

		:param _host: hostname or IP to connect to
		:param _port: port number to use
		:param _ledMap: List of aliases for LEDs
		:param _apikey: API key (password) to provide
		"""
		self.host = _host
		self.port = _port
		self.ledMap = _ledMap
		self.apikey = _apikey

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

	def getProfiles(self):
		"""
		Get a list of profile names.

		:returns: list of strings
		"""
		cmd = 'getprofiles\n'
		self.connection.send(cmd)
		profiles = self.__readResult()
		return profiles.split(':')[1].rstrip(';').split(';')

	def getProfile(self):
		"""
		Get the name of the currently active profile.

		:returns: string
		"""
		cmd = 'getprofile\n'
		self.connection.send(cmd)
		profile = self.__readResult()
		profile = profile.split(':')[1]
		return profile

	def getStatus(self):
		"""
		Get the status of the Lightpack (on or off)

		:returns: string, 'on' or 'off'
		"""
		cmd = 'getstatus\n'
		self.connection.send(cmd)
		status = self.__readResult()
		status = status.split(':')[1]
		return status

	def getCountLeds(self):
		"""
		Get the number of LEDs the Lightpack controls.

		:returns: integer
		"""
		cmd = 'getcountleds\n'
		self.connection.send(cmd)
		count = self.__readResult()
		count = count.split(':')[1]
		return int(count)

	def getAPIStatus(self):
		cmd = 'getstatusapi\n'
		self.connection.send(cmd)
		status = self.__readResult()
		status = status.split(':')[1]
		return status

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
				cmd = 'apikey:' + self.apikey + '\n'
				self.connection.send(cmd)
				self.__readResult()
			return 0
		except:
			print 'Lightpack API server is missing'
			return -1

	def setColour(self, led, r, g, b):
		"""
		Set the specified LED to the specified colour.

		:param led: 0-based LED index or its preconfigured alias
		:type led: str or int
		:param r: Red value (0 to 255)
		:type r: int
		:param g: Green value (0 to 255)
		:type g: int
		:param b: Blue value (0 to 255)
		:type b: int
		"""
		cmd = 'setcolor:{0}-{1},{2},{3}\n'.format(self.__ledIndex(led), r, g, b)
		self.connection.send(cmd)
		self.__readResult()
	setColor = setColour

	def setColourToAll(self, r, g, b):
		"""
		Set all LEDs to the specified colour.

		:param r: Red value (0 to 255)
		:type r: int
		:param g: Green value (0 to 255)
		:type g: int
		:param b: Blue value (0 to 255)
		:type b: int
		"""
		cmdstr = ''
		for i in range(len(self.ledMap)):
			cmdstr = str(cmdstr) + str(self.__ledIndex(i)) + '-{0},{1},{2};'.format(r,g,b)
		cmd = 'setcolor:' + cmdstr + '\n'
		self.connection.send(cmd)
		self.__readResult()
	setColorToAll = setColourToAll

	def setGamma(self, g):
		cmd = 'setgamma:{0}\n'.format(g)
		self.connection.send(cmd)
		self.__readResult()

	def setSmooth(self, s):
		cmd = 'setsmooth:{0}\n'.format(s)
		self.connection.send(cmd)
		self.__readResult()

	def setBrightness(self, s):
		cmd = 'setbrightness:{0}\n'.format(s)
		self.connection.send(cmd)
		self.__readResult()

	def setProfile(self, profile):
		"""
		Set the current Lightpack profile.

		:param profile: profile to activate
		:type profile: str
		"""
		cmd = 'setprofile:%s\n' % p
		self.connection.send(cmd)
		self.__readResult()

	def lock(self):
		"""
		Lock the Lightpack, thereby assuming control.

		While locked, the Lightpack's other functionality will be frozen. For 
		instance, it won't capture from the screen and update its colours while 
		locked.
		"""
		cmd = 'lock\n'
		self.connection.send(cmd)
		self.__readResult()

	def unlock(self):
		"""
		Unlock the Lightpack, thereby releasing control to other processes.
		"""
		cmd = 'unlock\n'
		self.connection.send(cmd)
		self.__readResult()

	def __setStatus(self, status):
		"""
		Set the status to a given string.

		:param status: status to set
		:type status: str
		"""
		cmd = 'setstatus:%s\n' % status
		self.connection.send(cmd)
		self.__readResult()

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
