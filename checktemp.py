# -*- coding: utf-8 -*-
#!/usr/bin/env python
import random
import time
import sys
import config as config
from Adafruit_BME280 import *
def checktemp():
    sensor = BME280(address = config.I2C_ADDRESS)
    while 1:
        temperature = sensor.read_temperature()
        humidity = sensor.read_humidity()
        preasure = sensor.read_pressure()
        print ("温度：%s  湿度：%s  气压：%s\n" % (temperature,humidity,preasure))
        time.sleep(config.MESSAGE_TIMESPAN / 1000.0)
if __name__ == "__main__":
    print ( "\nPython %s" % sys.version )
    print ( " 设备程序已启动" )
    checktemp()
