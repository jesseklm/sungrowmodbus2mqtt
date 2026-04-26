FROM python:3.14-alpine AS builder
ADD https://astral.sh/uv/0.11.7/install.sh /uv-installer.sh
RUN sh /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_NO_DEV=1
ENV UV_PYTHON_DOWNLOADS=0
COPY --exclude=.git/ --exclude=.venv/ . /app
WORKDIR /app
RUN uv sync --locked

FROM python:3.14-alpine
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app
CMD [ "python", "sungrowmodbus2mqtt.py" ]
