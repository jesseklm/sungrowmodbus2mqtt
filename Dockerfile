FROM debian:12-slim

WORKDIR /usr/src/app

COPY . .

SHELL ["/bin/bash", "-c"]

RUN apt-get -y update && apt-get install -y build-essential git pypy3 pypy3-venv && \
    pypy3 -m venv venv && \
    source venv/bin/activate && \
    pip install --no-cache-dir --prefer-binary -r requirements.txt && \
    apt-get remove -y build-essential git && \
    apt-get autoremove -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

CMD [ "venv/bin/pypy3", "./sungrowmodbus2mqtt.py" ]
