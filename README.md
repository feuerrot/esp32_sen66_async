# async SEN66 on an ESP32

```
~/bin/esptool/esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460800 erase_flash
~/bin/esptool/esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460800 write_flash -z 0x1000 ESP32_GENERIC-20251209-v1.27.0.bin
for file in {max7219,mqtt_as,sen66.py,main.py}; do echo $file; ampy --port /dev/ttyUSB0 put $file; done
```