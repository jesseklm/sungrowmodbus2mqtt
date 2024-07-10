import logging
import queue
import threading
from time import sleep

import paho.mqtt.client as mqtt

from config import config


class MqttHandler:
    def __init__(self):
        self.mqttc: mqtt.Client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqttc.on_connect = self.mqtt_on_connect
        self.mqttc.username_pw_set(config['mqtt_username'], config['mqtt_password'])
        self.mqttc.will_set(config['mqtt_topic'] + 'available', 'offline', retain=True)
        self.mqttc.connect_async(host=config['mqtt_server'], port=config['mqtt_port'])
        self.mqttc.loop_start()

        self.publishing_queue = queue.Queue()

        self.publishing_thread = threading.Thread(target=self.publishing_handler, daemon=True)
        self.publishing_thread.start()

    def mqtt_on_connect(self, mqttc, userdata, flags, reason_code, properties):
        self.mqttc.publish(config['mqtt_topic'] + 'available', 'online', retain=True)
        logging.info('mqtt connected.')

    def publish(self, topic, payload, retain=False):
        self.publishing_queue.put({
            'topic': config['mqtt_topic'] + topic,
            'payload': payload,
            'retain': retain,
        })

    def publishing_handler(self):
        while True:
            message = self.publishing_queue.get()
            while not self.mqttc.is_connected():
                sleep(1)
            result = self.mqttc.publish(message['topic'], message['payload'], retain=message['retain'])
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logging.error(f'publish failed: {message} {result}.')
            self.publishing_queue.task_done()
