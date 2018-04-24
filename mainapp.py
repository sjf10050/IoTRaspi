# -*- coding: utf-8 -*-
#!/usr/bin/env python
import random
import time
import datetime
import sys
import psutil
import requests
from iothub_client import IoTHubClient, IoTHubClientError, IoTHubTransportProvider, IoTHubClientResult
from iothub_client import IoTHubMessage, IoTHubMessageDispositionResult, IoTHubError, DeviceMethodReturnValue
import config as config
from BME280SensorSimulator import BME280SensorSimulator
import RPi.GPIO as GPIO
from Adafruit_BME280 import *
import re

MINIMUM_POLLING_TIME = 9
RECEIVE_CONTEXT = 0
MESSAGE_COUNT = 0
TWIN_CONTEXT = 0
SEND_REPORTED_STATE_CONTEXT = 0
METHOD_CONTEXT = 0
TIMEOUT = config.TIMEOUT
MESSAGE_TIMEOUT = config.MESSAGE_TIMEOUT
MESSAGE_SWITCH = config.MESSAGE_SWITCH
FAN_SWITCH = config.FAN_SWITCH
TEMPERATURE_ALERT = config.TEMPERATURE_ALERT
TEMPERATURE_EMERGENCY = config.TEMPERATURE_EMERGENCY

# global counters
RECEIVE_CALLBACKS = 0
SEND_CALLBACKS = 0
BLOB_CALLBACKS = 0
TWIN_CALLBACKS = 0
SEND_REPORTED_STATE_CALLBACKS = 0
METHOD_CALLBACKS = 0
EVENT_SUCCESS = "success"
EVENT_FAILED = "failed"
PROTOCOL = IoTHubTransportProvider.MQTT
CONNECTION_STRING=config.CONNECTION_STRING
WECHATMESSAGE_STRING=config.WECHATMESSAGE_STRING
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(config.GPIO_PIN_ADDRESS, GPIO.OUT)
GPIO.setup(config.GPIO_FAN_ADDRESS, GPIO.OUT)
CONFIG_ID = "1"
TWIN_PAYLOAD = "{\"configId\":" + CONFIG_ID + ",\"sendFrequency\":\"24h\"}"
MSG_TXT = "{\"deviceId\": \"Raspberry-song\",\"temperature\": %f,\"humidity\": %f,\"CPU\": %f,\"memory\": %f}"
def is_correct_connection_string():
    m = re.search("HostName=.*;DeviceId=.*;", CONNECTION_STRING)
    if m:
        return True
    else:
        return False
if not is_correct_connection_string():
    print ( "!!Device connection string is Wrong." )
    telemetry.send_telemetry_data(None, EVENT_FAILED, "!!Device connection string is Wrong.")
    sys.exit(0)

def receive_message_callback(message, counter):
    global RECEIVE_CALLBACKS
    message_buffer = message.get_bytearray()
    size = len(message_buffer)
    print ( "Received Message [%d]:" % counter )
    print ( "    Data: <%s> & Size=%d" % (message_buffer[:size].decode("utf-8"), size) )
    map_properties = message.properties()
    key_value_pair = map_properties.get_internals()
    print ( "    Properties: %s" % key_value_pair )
    counter += 1
    RECEIVE_CALLBACKS += 1
    print ( "    Total calls received: %d" % RECEIVE_CALLBACKS )
    return IoTHubMessageDispositionResult.ACCEPTED


def send_confirmation_callback(message, result, user_context):
    global SEND_CALLBACKS
    print ( "Confirmation[%d] received for message with result = %s" % (user_context, result) )
    map_properties = message.properties()
    print ( "    message_id: %s" % message.message_id )
    print ( "    correlation_id: %s" % message.correlation_id )
    key_value_pair = map_properties.get_internals()
    print ( "    Properties: %s" % key_value_pair )
    SEND_CALLBACKS += 1
    print ( "    Total calls confirmed: %d" % SEND_CALLBACKS )
    led_blink()


def device_twin_callback(update_state, payload, user_context):
    global TWIN_CALLBACKS
    global CONFIG_ID
    desired_configId = payload[payload.find("configId")+11:payload.find("configId")+12]
    if CONFIG_ID != desired_configId:
        print ( "" )
        print ( "Reported pending config change: %s" % payload)
        desired_sendFrequency = payload[payload.find("sendFrequency")+17:payload.find("sendFrequency")+19]
        print ( "...desired configId: " + desired_configId)
        print ( "...desired sendFrequency: " + desired_sendFrequency)
        new_payload = "{\"configId\":" + desired_configId + ",\"sendFrequency\":\"" + desired_sendFrequency + "\"}"
        CLIENT.send_reported_state(new_payload, len(new_payload), send_reported_state_callback, SEND_REPORTED_STATE_CONTEXT)
        CONFIG_ID = desired_configId
    print ( "\nTwin callback called with:\nupdateStatus = %s\npayload = %s\ncontext = %s" % (update_state, payload, user_context) )
    TWIN_CALLBACKS += 1
    print ( "Total calls confirmed: %d\n" % TWIN_CALLBACKS )

def send_reported_state_callback(status_code, user_context):
    global SEND_REPORTED_STATE_CALLBACKS
    print ( "Confirmation for reported state received with:\nstatus_code = [%d]\ncontext = %s" % (status_code, user_context) )
    SEND_REPORTED_STATE_CALLBACKS += 1
    print ( "    Total calls confirmed: %d" % SEND_REPORTED_STATE_CALLBACKS )


def device_method_callback(method_name, payload, user_context):
    global METHOD_CALLBACKS,MESSAGE_SWITCH
    print ( "\nMethod callback called with:\nmethodName = %s\npayload = %s\ncontext = %s" % (method_name, payload, user_context) )
    METHOD_CALLBACKS += 1
    print ( "Total calls confirmed: %d\n" % METHOD_CALLBACKS )
    device_method_return_value = DeviceMethodReturnValue()
    device_method_return_value.response = "{ \"Response\": \"无响应\" }"
    device_method_return_value.status = 0
    if method_name == "messagestart":
        MESSAGE_SWITCH = True
        print ( "开始发送信息\n" )
        device_method_return_value.response = "{ \"Response\": \"成功启动消息发送\" }"
        return device_method_return_value
    if method_name == "messagestop":
        MESSAGE_SWITCH = False
        print ( "停止发送信息\n" )
        device_method_return_value.response = "{ \"Response\": \"成功终止消息发送\" }"
        return device_method_return_value
    if method_name == "checklive":
        led_blink()
        print ( "设备在线\n" )
        device_method_return_value.response = "{ \"Response\": \"设备在线\" }"
        device_method_return_value.status = 200
        return device_method_return_value
    if method_name == "RebootDevice":
        print ( "正在重启..." )
        
        
        #time.sleep(20)
        #设备重启逻辑
        
        
        device_method_return_value.response = "{ \"Response\": \"设备已重启\" }"
    if method_name == "ledblink":
        led_blink()
        print ( "指示灯已闪烁\n" )
        device_method_return_value.response = "{ \"Response\": \"成功闪烁\" }"
        device_method_return_value.status = 200
        return device_method_return_value
    if method_name == "fanon":
        fan_on()
        print ( "风扇已开启\n" )
        device_method_return_value.response = "{ \"Response\": \"成功开启风扇\" }"
        device_method_return_value.status = 200
        return device_method_return_value
    if method_name == "fanoff":
        fan_off()
        print ( "风扇已关闭\n" )
        device_method_return_value.response = "{ \"Response\": \"成功关闭风扇\" }"
        device_method_return_value.status = 200
        return device_method_return_value
    return device_method_return_value


def blob_upload_conf_callback(result, user_context):
    global BLOB_CALLBACKS
    print ( "Blob upload confirmation[%d] received for message with result = %s" % (user_context, result) )
    BLOB_CALLBACKS += 1
    print ( "    Total calls confirmed: %d" % BLOB_CALLBACKS )


def iothub_client_init():
    # prepare iothub client
    client = IoTHubClient(CONNECTION_STRING, PROTOCOL)
    client.set_option("设备信息", "智能监测设备python客户端")
    if client.protocol == IoTHubTransportProvider.HTTP:
        client.set_option("timeout", TIMEOUT)
        client.set_option("MinimumPollingTime", MINIMUM_POLLING_TIME)
    # set the time until a message times out
    client.set_option("messageTimeout", MESSAGE_TIMEOUT)
    # to enable MQTT logging set to 1
    if client.protocol == IoTHubTransportProvider.MQTT:
        client.set_option("logtrace", 0)
    client.set_message_callback(
        receive_message_callback, RECEIVE_CONTEXT)
    if client.protocol == IoTHubTransportProvider.MQTT or client.protocol == IoTHubTransportProvider.MQTT_WS:
        client.set_device_twin_callback(
            device_twin_callback, TWIN_CONTEXT)
        client.set_device_method_callback(
            device_method_callback, METHOD_CONTEXT)
    return client


def print_last_message_time(client):
    try:
        last_message = client.get_last_message_receive_time()
        print ( "Last Message: %s" % time.asctime(time.localtime(last_message)) )
        print ( "Actual time : %s" % time.asctime() )
    except IoTHubClientError as iothub_client_error:
        if iothub_client_error.args[0].result == IoTHubClientResult.INDEFINITE_TIME:
            print ( "未收到消息" )
        else:
            print ( iothub_client_error )

def update_reboottime(client):
    current_time = str(datetime.datetime.now())
    reported_state = "{\"rebootTime\":\"" + current_time + "\"}"
    client.send_reported_state(reported_state, len(reported_state), send_reported_state_callback, SEND_REPORTED_STATE_CONTEXT)
    print ( "Updating device twins: rebootTime" )

def iothub_client_sample_run():
    try:
        client = iothub_client_init()
        client.send_reported_state(TWIN_PAYLOAD, len(TWIN_PAYLOAD), send_reported_state_callback, SEND_REPORTED_STATE_CONTEXT)
        if client.protocol == IoTHubTransportProvider.MQTT:
            #update_reboottime(client)
            reported_state = "{\"newState\":\"standBy\"}"
            client.send_reported_state(reported_state, len(reported_state), send_reported_state_callback, SEND_REPORTED_STATE_CONTEXT)
            print ( "客户端准备就绪 ")
        if not config.SIMULATED_DATA:
            sensor = BME280(address = config.I2C_ADDRESS)
        else:
            sensor = BME280SensorSimulator()
        while True:
            global MESSAGE_COUNT,MESSAGE_SWITCH
            if MESSAGE_SWITCH:
                # send a few messages every minute
                print ( "IoTHubClient sending %d messages" % MESSAGE_COUNT )
                cpu_percent= psutil.cpu_percent()
                memory = psutil.virtual_memory()
                memorypercent=float(memory.used)/float(memory.total)
                temperature = sensor.read_temperature()
                humidity = sensor.read_humidity()
                msg_txt_formatted = MSG_TXT % (
                    temperature,
                    humidity,                   
                    cpu_percent,
                    memorypercent)
                print (msg_txt_formatted)
                message = IoTHubMessage(msg_txt_formatted)
                # optional: assign ids
                message.message_id = "message_%d" % MESSAGE_COUNT
                message.correlation_id = "correlation_%d" % MESSAGE_COUNT
                # optional: assign properties
                prop_map = message.properties()
                prop_map.add("temperatureAlert", "true" if temperature > TEMPERATURE_ALERT else "false")
                client.send_event_async(message, send_confirmation_callback, MESSAGE_COUNT)
                print ( "IoTHubClient.send_event_async accepted message [%d] for transmission to IoT Hub." % MESSAGE_COUNT )
                status = client.get_send_status()
                print ( "Send status: %s" % status )
                MESSAGE_COUNT += 1
                print ( "" )
            time.sleep(config.MESSAGE_TIMESPAN / 1000.0)
            temperature = sensor.read_temperature()
            if temperature > TEMPERATURE_EMERGENCY :
                if not FAN_SWITCH:
                    fan_on()#测试代码
                    sendTempAlarm(temperature)
            if temperature < TEMPERATURE_EMERGENCY :
                if FAN_SWITCH:
                    fan_off()#测试代码
        
    except IoTHubError as iothub_error:
        print ( "Unexpected error %s from IoTHub" % iothub_error )
        return
    except KeyboardInterrupt:
        #reported_state = "{\"newState\":\"offline\"}"
        #client.send_reported_state(reported_state, len(reported_state), send_reported_state_callback, SEND_REPORTED_STATE_CONTEXT)
        print ( "客户端被终止工作" )

    print_last_message_time(client)

def led_blink():
    GPIO.output(config.GPIO_PIN_ADDRESS, GPIO.HIGH)
    time.sleep(config.BLINK_TIMESPAN / 1000.0)
    GPIO.output(config.GPIO_PIN_ADDRESS, GPIO.LOW)
def sendTempAlarm(temp):
    r = requests.post(WECHATMESSAGE_STRING, data={'text': "温度报警", 'desp': temp})
def sendmessage(title,maintext):
    r = requests.post(WECHATMESSAGE_STRING, data={'text': title, 'desp': maintext})

def fan_on():
    GPIO.output(config.GPIO_FAN_ADDRESS, GPIO.HIGH)
def fan_off():
    GPIO.output(config.GPIO_FAN_ADDRESS, GPIO.LOW)
def usage():
    print ( "Usage: iothub_client_sample.py -p <protocol> -c <connectionstring>" )
    print ( "    protocol        : <amqp, amqp_ws, http, mqtt, mqtt_ws>" )
    print ( "    connectionstring: <HostName=<host_name>;DeviceId=<device_id>;SharedAccessKey=<device_key>>" )
def parse_iot_hub_name():
    m = re.search("HostName=(.*?)\.", CONNECTION_STRING)
    return m.group(1)

if __name__ == "__main__":
    print ( "\nPython %s" % sys.version )
    print ( " 设备程序已启动" )
    
    iothub_client_sample_run()
