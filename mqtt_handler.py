import logging
import queue
import threading
import time
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.client import ConnectFlags
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode


class MqttHandler:
    def __init__(self, config: dict) -> None:
        self.topic_prefix: str = config.get('mqtt_topic', 'sungrowmodbus2mqtt/').rstrip('/') + '/'
        self.host: str = config['mqtt_server']
        self.port: int = config.get('mqtt_port', 1883)

        self.mqttc: mqtt.Client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqttc.on_connect = self.on_connect
        self.mqttc.username_pw_set(config['mqtt_username'], config['mqtt_password'])
        self.mqttc.will_set(self.topic_prefix + 'available', 'offline', retain=True)
        self.mqttc.connect_async(host=self.host, port=self.port)
        self.mqttc.loop_start()

        self.publishing_queue: queue.Queue[dict[str, Any]] = queue.Queue()

        self.publishing_thread: threading.Thread = threading.Thread(target=self.publishing_handler, daemon=True)
        self.publishing_thread.start()

    def on_connect(self, client: mqtt.Client, userdata: Any, connect_flags: ConnectFlags, reason_code: ReasonCode,
                   properties: Properties | None) -> None:
        self.mqttc.publish(self.topic_prefix + 'available', 'online', retain=True)
        if reason_code == ReasonCode(PacketTypes.CONNACK, 'Success'):
            logging.info('mqtt connected.')
        else:
            logging.error(f'mqtt connection to %s:%s failed, %s.', self.host, self.port, reason_code)

    def publish(self, topic: str, payload: str | int | float, retain=False) -> None:
        self.publishing_queue.put({
            'topic': self.topic_prefix + topic,
            'payload': payload,
            'retain': retain,
        })

    def publishing_handler(self) -> None:
        while True:
            message: dict[str, Any] = self.publishing_queue.get()
            while not self.mqttc.is_connected():
                time.sleep(1)
            result: mqtt.MQTTMessageInfo = self.mqttc.publish(**message)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                logging.error(f'mqtt publish failed: %s %s.', message, result)
            self.publishing_queue.task_done()
