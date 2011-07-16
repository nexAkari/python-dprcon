#!/usr/bin/env python2

import socket, re, sys, md4, hmac, random, time

class RCONException(Exception):
	pass

class RCONConnectionRequiredException(RCONException):
	pass

class RCONAlreadyConnectedException(RCONException):
	pass

def requireConnected(f):
	def wrapper(self, *args, **kwargs):
		if not self.isConnected():
			raise RCONConnectionRequiredException
		
		return f(self, *args, **kwargs)
	
	wrapper.__doc__ = f.__doc__
	return wrapper

def requireDisconnected(f):
	def wrapper(self, *args, **kwargs):
		if self.isConnected():
			raise RCONAlreadyConnectedException
		
		return f(self, *args, **kwargs)
	
	wrapper.__doc__ = f.__doc__
	return wrapper 

responseRegexp = re.compile("\377\377\377n(.*)", re.S)

class InsecureRCONConnection(object):
	def __init__(self, host, port, password, connect=False, bufsize=1024):
		self.__host = host
		self.__port = port
		self.__pwd  = password
		self.__sock = None
		self.bufsize = bufsize
		
		if connect:
			self.connect()
	
	def __del__(self):
		try:
			self.disconnect()
		except RCONAlreadyConnectedException:
			pass
	
	@requireDisconnected
	def connect(self):
		self.__sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.__sock.connect((self.__host, self.__port))

	def isConnected(self):
		return self.__sock is not None
	
	@requireConnected
	def disconnect(self):
		self.__sock.close()
		self.__sock = None
		self.__addr = None
	
	@requireConnected
	def getLocalAddress(self):
		return "%s:%i" % self.__sock.getsockname()
	
	def makeRCONMessage(self, s):
		return "\377\377\377\377rcon %s %s" %(self.__pwd, s)
	
	def translateRCONResponse(self, s):
		try:
			return responseRegexp.findall(s)[0]
		except IndexError:
			return ""
	
	@requireConnected
	def send(self, *s):
		return self.__sock.send('\0'.join([self.makeRCONMessage(a) for a in s]))
	
	@requireConnected
	def read(self, bufsize=None):
		if bufsize is None:
			bufsize = self.bufsize
		
		return self.translateRCONResponse(self.__sock.recv(1024))
	
	def getSocket(self):
		return self.__sock
	

class TimeBasedSecureRCONConnection(InsecureRCONConnection):
	def makeRCONMessage(self, line):
		mytime = "%ld.%06d" %(time.time(), random.randrange(1000000))
		return "\377\377\377\377srcon HMAC-MD4 TIME %s %s %s" %(
			hmac.new(self.__pwd, "%s %s" % (mytime, line), digestmod=md4.new).digest(),
			mytime, line
		)

if __name__ == "__main__":
	host = raw_input("Server: ")
	port = int(raw_input("Port: "))
	sec  = int(raw_input("Security (as in rcon_secure): "))
	pwd  = raw_input("Password: ")
	
	try:
		rcon = {
			0:	InsecureRCONConnection,
			1:	TimeBasedSecureRCONConnection
		}[sec](host, port, pwd, connect=True)
	except KeyError as e:
		print "Invalid security value:", sec
		quit(0)

	print "Connected!"
	
	rcon.getSocket().settimeout(1)
	
	while True:
		rcon.send(raw_input("Command: "))
		print "Response follows: "
		
		def getresponse():
			try:
				return rcon.read()
			except socket.error:
				return None
		
		r = getresponse()
		while r is not None:
			sys.stdout.write(r)
			r = getresponse()
	
