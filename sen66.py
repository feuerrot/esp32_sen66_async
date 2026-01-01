import ustruct
import utime

CMD_START = b"\x00\x21"
CMD_READ = b"\x03\x00"
CMD_STOP = b"\x01\x04"
CMD_READY = b"\x02\x02"
CMD_RESET = b"\xd3\x04"
CMD_STATUS = b"\xd2\x06"

class SEN66:
	def __init__(self, i2c, address=0x6b):
		self.i2c = i2c
		self.address = address
		self.value = None

	def _read(self, location, length):
		self.i2c.writeto(self.address, location)
		return self.i2c.readfrom(self.address, length)

	def _write(self, command, data=None):
		if data:
			pass

		self.i2c.writeto(self.address, command)

	def _crc8(self, data):
		crc = 0xFF

		for elem in data:
			crc ^= elem

			for shift in range(8):
				if (crc & 0x80):
					crc = ((crc << 1) ^ 0x31) % 0x100
				else:
					crc = crc << 1

		return crc

	def check_crc(self, data):
		for offset in range(0, len(data), 3):
			if not data[offset+2] == self._crc8(data[offset:offset+2]):
				print("SEN66: Wrong CRC at {}: {}".format (offset, data[offset:offset+3]))
				return False
		return True

	def reset(self):
		try:
			self._write(CMD_STOP)
		except:
			pass
		try:
			self._write(CMD_RESET)
		except:
			pass

	def status(self):
		status_raw = self._read(CMD_STATUS, 6)
		status_crc = self.check_crc(status_raw)
		if not status_crc:
			print("SEN66 status CRC wrong")
		print(status_raw)

	def start(self):
		self._write(CMD_START)

	@property
	def ready(self):
		ready_raw = self._read(CMD_READY, 3)
		ready_crc = self.check_crc(ready_raw)
		if not ready_crc:
			raise Exception("SEN66 READY CRC wrong: {}".format(ready_raw))
		ready = ustruct.unpack(">H", ready_raw[0:2])[0] & 0x07ff
		return bool(ready)

	def read(self):
		if not self.ready:
			return False

		data_raw = self._read(CMD_READ, 27)
		data_crc = self.check_crc(data_raw)
		if not data_crc:
			raise Exception("SEN66 READ CRC wrong: {}".format(data_raw))
		
		self.value = {}

		self.value["pm1u0"] = ustruct.unpack(">H", data_raw[0:2])[0] / 10
		self.value["pm2u5"] = ustruct.unpack(">H", data_raw[3:5])[0] / 10
		self.value["pm4u0"] = ustruct.unpack(">H", data_raw[6:8])[0] / 10
		self.value["pm10u"] = ustruct.unpack(">H", data_raw[9:11])[0] / 10

		self.value["humidity"] = ustruct.unpack(">h", data_raw[12:14])[0] / 100
		self.value["temperature"] = ustruct.unpack(">h", data_raw[15:17])[0] / 200
		self.value["voc"] = ustruct.unpack(">h", data_raw[18:20])[0] / 10
		self.value["nox"] = ustruct.unpack(">h", data_raw[21:23])[0] / 10
		self.value["co2"] = ustruct.unpack(">H", data_raw[24:26])[0]

		self.value["timestamp"] = utime.time()

		return True

	@property
	def values(self):
		return self.value


