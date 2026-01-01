import time
import struct
import machine
import ubinascii
import bluetooth

import sen66
import max7219

import asyncio
import mqtt_as

DEBUG=False
WIFI_ESSID="essid"
WIFI_PSK="psk"
MQTT_SERVER="server"

ble_name = "feuerrot:SEN66"
ble_appearance = b'\x42\x05'
ble_adv_interval = 50000

def debug(text):
	if DEBUG:
		print(text)

class Sensor:
	async def run(self):
		try:
			self.UID = ubinascii.hexlify(machine.unique_id()).decode()
			sda = machine.Pin(19, machine.Pin.IN, machine.Pin.PULL_UP)
			scl = machine.Pin(22, machine.Pin.IN, machine.Pin.PULL_UP)
			self.I2C = machine.I2C(0, sda=sda, scl=scl, freq=100000)
			self.SEN = sen66.SEN66(self.I2C)
			self.SEN.reset()
			self.LED = max7219.max7219()
			self.LED.set_intensity(max7219.INTENSITY_15)
			self.event = asyncio.Event()
			self.ble = bluetooth.BLE()
			self.ble.active(True)
		except Exception as e:
			print(e)
			time.sleep(1)
			machine.reset()

		debug("init")
		self.SEN.start()
		await asyncio.sleep_ms(100)
		await self.init_mqtt()
		asyncio.create_task(self.mqtt_up())
		await self.mqtt.connect()


		await asyncio.gather(
			asyncio.create_task(self.read_sensor()),
			asyncio.create_task(self.update_display()),
			asyncio.create_task(self.publish_sensor_mqtt()),
			asyncio.create_task(self.publish_sensor_ble())
		)


	async def update_display(self):
		field = 0
		while True:
			debug("update_display")
			try:
				await self.event.wait()
				self.event.clear()
				data = self.SEN.values
				if data:
					if field == 0:
						self.LED.write_string("CO2{: >5}".format(int(data["co2"])))
					elif field == 1:
						self.LED.write_string("{: >2}\xb0C{: >2}\xb0o".format(
							int(data["temperature"]),
							int(data["humidity"])
						))
					elif field == 2:
						self.LED.write_string("P4 {: >5}".format(int(data["pm4u0"])))
					elif field == 3:
						self.LED.write_string("P10 {: >4}".format(int(data["pm10u"])))
					elif field == 4:
						self.LED.write_string("UOC {: >4}".format(int(data["voc"])))
					elif field == 5:
						self.LED.write_string("noH {: >4}".format(int(data["nox"])))

					field = (field+1)%6
			except ValueError:
				pass
			await asyncio.sleep_ms(1000)

	async def read_sensor(self):
		while True:
			debug("read_sensor")
			try:
				success = self.SEN.read()
			except Exception as e:
				print(f"read_sensor: {e}")
				await asyncio.sleep_ms(2000)
				continue
			if not success:
				try:
					print(f"read_sensor: status: {self.SEN.status()}")
				except:
					pass
				print("read_sensor: SEN66 not ready")
				await asyncio.sleep_ms(2000)
				continue

			print(self.SEN.values)
			self.event.set()
			await asyncio.sleep_ms(1200)

	async def publish_sensor_mqtt(self):
		while True:
			debug("publish_sensor_mqtt")
			await self.event.wait()
			data = self.SEN.values

			if not data:
				continue
			
			try:
				(pm1u0, pm2u5, pm4u0, pm10u, humidity, temperature, voc, nox, co2) = \
					data["pm1u0"], \
					data["pm2u5"], \
					data["pm4u0"], \
					data["pm10u"], \
					data["humidity"], \
					data["temperature"], \
					data["voc"], \
					data["nox"], \
					data["co2"]
			except KeyError as e:
				print(f"publish_sensor_mqtt: key error: {e}\ndata: {data}")
				continue


			await self.mqtt.publish(f"sensor/{self.UID}/sen66/co2", str(co2))
			await self.mqtt.publish(f"sensor/{self.UID}/sen66/temperature", str(temperature))
			await self.mqtt.publish(f"sensor/{self.UID}/sen66/humidity", str(humidity))
			await self.mqtt.publish(f"sensor/{self.UID}/sen66/pm1.0", str(pm1u0))
			await self.mqtt.publish(f"sensor/{self.UID}/sen66/pm2.5", str(pm2u5))
			await self.mqtt.publish(f"sensor/{self.UID}/sen66/pm4.0", str(pm4u0))
			await self.mqtt.publish(f"sensor/{self.UID}/sen66/pm10", str(pm10u))
			await self.mqtt.publish(f"sensor/{self.UID}/sen66/voc", str(voc))
			await self.mqtt.publish(f"sensor/{self.UID}/sen66/nox", str(nox))

			await asyncio.sleep_ms(2000)

	async def mqtt_up(self):
		while True:
			await self.mqtt.up.wait()
			self.mqtt.up.clear()
			print("mqtt: connected")

	async def publish_sensor_ble(self):
		while True:
			debug("publish_sensor_ble")
			await self.event.wait()
			try:
				data = self.SEN.values

				if not data:
					continue
			except KeyError as e:
				print(f"publish_sensor_ble: key error: {e}\ndata: {data}")
				continue

			rdata = bytearray(b'\xff\xff') # no manufacturer
			rdata.append(0) # version
			rdata.extend(struct.pack("<H", int(data['temperature']*100)))
			rdata.extend(struct.pack("<H", int(data['humidity']*100)))
			rdata.extend(struct.pack("<H", int(data['pm1u0']*10)))
			rdata.extend(struct.pack("<H", int(data['pm2u5']*10)))
			rdata.extend(struct.pack("<H", int(data['pm4u0']*10)))
			rdata.extend(struct.pack("<H", int(data['pm10u']*10)))
			rdata.extend(struct.pack("<H", data['co2']))
			rdata.extend(struct.pack("<H", int(data['voc']*10)))
			rdata.extend(struct.pack("<H", int(data['nox']*10)))

			# advertisement every ble_adv_interval μs
			adv = bytearray()
			adv.extend(b'\x02\x01\x06') # (len, content, flags)
			adv.extend(struct.pack('BB', len(rdata)+1, 0xff) + rdata)
			debug(f"publish_sensor_ble: len adv: {len(adv)}")

			# scan response data
			resp = bytearray()
			resp.extend(struct.pack('BB', len(ble_appearance) + 1, 0x19) + ble_appearance)
			resp.extend(struct.pack('BB', len(ble_name)+1, 0x09) + ble_name)
			debug(f"publish_sensor_ble: len resp: {len(resp)}")

			try:
				self.ble.gap_advertise(
					ble_adv_interval,
					adv_data=adv,
					resp_data=resp,
					connectable=False
				)
			except OSError:
				print("publish_sensor_ble: OSError while gap_advertise")
			await asyncio.sleep_ms(500)

	async def init_mqtt(self):
		debug("init_mqtt")
		config = mqtt_as.config
		config['server'] = MQTT_SERVER
		config['ssid'] = WIFI_ESSID
		config['wifi_pw'] = WIFI_PSK
		config['client_id'] = f"Sensor_{self.UID}"
		config["queue_len"] = 1
		self.mqtt = mqtt_as.MQTTClient(config)


print("Boot complete")
time.sleep(2)
sensor = Sensor()
asyncio.run(sensor.run())


