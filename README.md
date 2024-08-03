# sungrowmodbus2mqtt

Sungrow SH5.0RT / SH6.0RT / SH8.0RT / SH10RT Modbus TCP to MQTT.
Small and efficient.

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
    image: ghcr.io/jesseklm/sungrowmodbus2mqtt:v1.0.3
    restart: unless-stopped
    volumes:
      - ./config.sh10rt.yaml:/etc/nginx/conf.d:ro
```

- `wget -O config.sh10rt.yaml https://raw.githubusercontent.com/jesseklm/sungrowmodbus2mqtt/v1.0.3/config.sh10rt.example.yaml`
- adjust your config yaml
- `docker compose up -d`
