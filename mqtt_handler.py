import logging
import queue
import threading
from time import sleep

import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.reasoncodes import ReasonCode


class MqttHandler:
    def __init__(self, config: dict):
        self.topic_prefix: str = config.get('mqtt_topic', 'sungrowmodbus2mqtt/')
        if not self.topic_prefix.endswith('/'):
            self.topic_prefix += '/'

        self.mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqttc.on_connect = self.on_connect
        self.mqttc.username_pw_set(config['mqtt_username'], config['mqtt_password'])
        self.mqttc.will_set(self.topic_prefix + 'available', 'offline', retain=True)
        self.host: str = config['mqtt_server']
        self.port: int = config.get('mqtt_port', 1883)
        self.mqttc.connect_async(host=self.host, port=self.port)
        self.mqttc.loop_start()

        self.publishing_queue = queue.Queue()

        self.publishing_thread = threading.Thread(target=self.publishing_handler, daemon=True)
        self.publishing_thread.start()

    def on_connect(self, client, userdata, connect_flags, reason_code, properties):
        self.mqttc.publish(self.topic_prefix + 'available', 'online', retain=True)
        if reason_code == ReasonCode(PacketTypes.CONNACK, 'Success'):
            logging.info('mqtt connected.')
        else:
            logging.error(f'mqtt connection to %s:%s failed, %s.', self.host, self.port, reason_code)

    def publish(self, topic: str, payload: str | int | float, retain=False):
        self.publishing_queue.put({
            'topic': self.topic_prefix + topic,
            'payload': payload,
            'retain': retain,
        })

    def publishing_handler(self):
        while True:
            message: dict = self.publishing_queue.get()
            while not self.mqttc.is_connected():
                sleep(1)
            result = self.mqttc.publish(message['topic'], message['payload'], retain=message['retain'])
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logging.error(f'mqtt publish failed: %s %s.', message, result)
            self.publishing_queue.task_done()
