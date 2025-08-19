import hashlib
import logging

from gmqtt import Client as MQTTClient, Message, Subscription

from ha_discovery import send_ha_discovery


class MqttHandler:
    def __init__(self, config: dict, sub_topics=None, message_callback=None) -> None:
        self.topic_prefix: str = config.get('mqtt_topic', 'sungrowmodbus2mqtt/').rstrip('/') + '/'
        self.host: str = config['mqtt_server']
        self.port: int = config.get('mqtt_port', 1883)
        self.subscriptions = []
        if sub_topics:
            for sub_topic in sub_topics:
                logging.debug('mqtt subscribing %s%s/set', self.topic_prefix, sub_topic)
                self.subscriptions.append(Subscription(self.topic_prefix + sub_topic + '/set'))
        self.message_callback = message_callback

        client_id = hashlib.md5(f'm2mqtt-{self.host}{self.port}{self.topic_prefix}'.encode()).hexdigest()
        will_message: Message = Message(self.topic_prefix + 'available', 'offline', will_delay_interval=5, retain=True)
        self.mqttc: MQTTClient = MQTTClient(client_id=client_id, will_message=will_message)
        self.mqttc.on_connect = self.on_connect
        self.mqttc.on_message = self.on_message
        self.mqttc.set_auth_credentials(config['mqtt_username'], config['mqtt_password'])
        self.first_connect = True
        self.ha_config = config

    def on_connect(self, client, flags, rc, properties):
        client.publish(self.topic_prefix + 'available', 'online', retain=True)
        logging.info('mqtt connected.')
        if client.subscriptions:
            client._connection.subscribe(client.subscriptions)
        elif self.subscriptions:
            client.subscribe(self.subscriptions)
        if self.first_connect:
            self.first_connect = False
            send_ha_discovery(self.ha_config, self.topic_prefix, self.mqttc.publish)
            self.ha_config = None

    async def on_message(self, client, topic, payload, qos, properties):
        logging.debug('mqtt message: topic: %s, payload: %s', topic, payload)
        if self.message_callback:
            topic = topic.removeprefix(self.topic_prefix).removesuffix('/set')
            await self.message_callback(topic, payload.decode().strip())
        return 0

    def publish(self, topic: str, payload: str | int | float, retain: bool = False) -> None:
        self.mqttc.publish(self.topic_prefix + topic, payload, retain=retain)

    async def connect(self) -> bool:
        if self.mqttc.is_connected:
            return True
        try:
            await self.mqttc.connect(self.host, self.port)
            return True
        except ConnectionRefusedError as e:
            logging.warning(f'mqtt: {self.host=}, {e=}')
        except Exception as e:
            logging.error(f'mqtt: {self.host=}, {e=}')
        return False

    async def disconnect(self):
        if self.mqttc.is_connected:
            await self.mqttc.disconnect(reason_code=4)
            logging.info('mqtt disconnected.')
