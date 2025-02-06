import logging

from gmqtt import Client as MQTTClient, Message


class MqttHandler:
    def __init__(self, config: dict) -> None:
        self.topic_prefix: str = config.get('mqtt_topic', 'sungrowmodbus2mqtt/').rstrip('/') + '/'
        self.host: str = config['mqtt_server']
        self.port: int = config.get('mqtt_port', 1883)

        will_message: Message = Message(self.topic_prefix + 'available', 'offline', will_delay_interval=5, retain=True)
        self.mqttc: MQTTClient = MQTTClient(client_id=None, will_message=will_message)
        self.mqttc.on_connect = self.on_connect
        self.mqttc.set_auth_credentials(config['mqtt_username'], config['mqtt_password'])

    def on_connect(self, client, flags, rc, properties):
        client.publish(self.topic_prefix + 'available', 'online', retain=True)
        logging.info('mqtt connected.')

    def publish(self, topic: str, payload: str | int | float, retain: bool = False) -> None:
        self.mqttc.publish(self.topic_prefix + topic, payload, retain=retain)

    async def connect(self) -> bool:
        if self.mqttc.is_connected:
            return True
        try:
            await self.mqttc.connect(self.host, self.port)
            return True
        except ConnectionRefusedError as e:
            logging.warning(f"mqtt: {self.host=}, {e=}")
        except Exception as e:
            logging.error(f"mqtt: {self.host=}, {e=}")
        return False

    async def disconnect(self):
        if self.mqttc.is_connected:
            await self.mqttc.disconnect(reason_code=4)
            logging.info('mqtt disconnected.')
