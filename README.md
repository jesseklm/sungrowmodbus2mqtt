# sungrowmodbus2mqtt

Sungrow inverter Modbus TCP to MQTT.
Small and efficient.

Devices: SH3.0-6.0RS / SH8.0-10RS / SH5.0-10RT / SH5-25T

Tested: SH10RT

## run as Home Assistant Addon

- add `https://github.com/jesseklm/hassio-addons` as Add-on Repository
- install sungrowmodbus2mqtt
- set your configuration:
  - mqtt_server: addon_core_mosquitto for internal Home Assistant Mosquitto Addon, hostname or ip otherwise
  - mqtt_port: 1883 if not changed otherwise
  - mqtt_username: your mqtt user
  - mqtt_password: your mqtt password
  - mqtt_topic: topic where to post in
  - ip: ip-adress of your sungrow inverter
- run

## run with docker compose

### docker compose

```yaml
services:
  sungrowmodbus2mqtt:
    container_name: sungrowmodbus2mqtt
    image: ghcr.io/jesseklm/sungrowmodbus2mqtt:1.0.22
    restart: unless-stopped
    volumes:
      - ./config.sh10rt.yaml:/config/config.yaml:ro
```

- `wget -O config.sh10rt.yaml https://raw.githubusercontent.com/jesseklm/sungrowmodbus2mqtt/1.0.22/config.sh10rt.example.yaml`
- adjust your config yaml
- `docker compose up -d`
