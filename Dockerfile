FROM pypy:3.10-slim

WORKDIR /usr/src/app

COPY . .

RUN apt-get -y update && apt-get install -y build-essential git && \
    pip install --no-cache-dir --prefer-binary -r requirements.txt && \
    apt-get remove -y build-essential git && \
    apt-get autoremove -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

CMD [ "pypy", "./sungrowmodbus2mqtt.py" ]
