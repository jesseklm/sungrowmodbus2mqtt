import logging
import queue
import threading
from time import sleep

import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.reasoncodes import ReasonCode

from config import config


class MqttHandler:
    def __init__(self):
        self.topic_prefix = config.get('mqtt_topic', 'sungrowmodbus2mqtt/')
        if not self.topic_prefix.endswith('/'):
            self.topic_prefix += '/'

        self.mqttc: mqtt.Client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqttc.on_connect = self.on_connect
        self.mqttc.username_pw_set(config['mqtt_username'], config['mqtt_password'])
        self.mqttc.will_set(self.topic_prefix + 'available', 'offline', retain=True)
        self.host = config['mqtt_server']
        self.port = config.get('mqtt_port', 1883)
        self.mqttc.connect_async(host=self.host, port=self.port)
        self.mqttc.loop_start()

        self.task_queue = queue.Queue()

        self.tasks_thread = threading.Thread(target=self.task_handler, daemon=True)
        self.tasks_thread.start()

    def on_connect(self, client, userdata, connect_flags, reason_code, properties):
        self.mqttc.publish(self.topic_prefix + 'available', 'online', retain=True)
        if reason_code == ReasonCode(PacketTypes.CONNACK, 'Success'):
            logging.info('mqtt connected.')
        else:
            logging.error(f'mqtt connection to {self.host}:{self.port} failed, {reason_code}.')

    def publish(self, topic, payload, retain=False):
        self.task_queue.put({
            'topic': f'{self.topic_prefix}{topic}',
            'payload': payload,
            'retain': retain,
        })

    def subscribe(self, topic):
        self.task_queue.put({
            'subscribe': f'{self.topic_prefix}{topic}',
        })

    def task_handler(self):
        while True:
            message = self.task_queue.get()
            while not self.mqttc.is_connected():
                sleep(1)
            if 'subscribe' in message:
                result, _ = self.mqttc.subscribe(message['subscribe'])
                if result != mqtt.MQTT_ERR_SUCCESS:
                    logging.error(f'mqtt subscribe failed: {message} {result}.')
            else:
                result = self.mqttc.publish(message['topic'], message['payload'], retain=message['retain'])
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    logging.error(f'mqtt publish failed: {message} {result}.')
            self.task_queue.task_done()
