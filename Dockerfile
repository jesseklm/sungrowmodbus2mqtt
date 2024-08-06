FROM python:3.12-alpine

WORKDIR /usr/src/app

COPY . .

ENV PYTHONPATH=/usr/lib/python3.12/site-packages

RUN apk --no-cache add py3-pycryptodomex && \
    pip install --no-cache-dir --prefer-binary -r requirements.txt

CMD [ "python", "./sungrowmodbus2mqtt.py" ]
