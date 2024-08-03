FROM pypy:3.10-slim

WORKDIR /usr/src/app

COPY . .

RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

CMD [ "pypy", "./sungrowmodbus2mqtt.py" ]
