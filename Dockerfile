# not using python:3.*-alpine cause glib-dev package depends python3
# https://pkgs.alpinelinux.org/package/v3.11/main/aarch64/glib-dev
FROM alpine:3.11

RUN apk add --no-cache \
    gcc \
    glib-dev \
    make \
    musl-dev \
    tini

RUN pip3 install pipenv

ARG SOURCE_DIR_PATH=/switchbot-mqtt
ARG SWITCHBOT_MQTT_VERSION=
COPY . $SOURCE_DIR_PATH
WORKDIR $SOURCE_DIR_PATH
ENV PIPENV_VENV_IN_PROJECT=yeah
RUN SETUPTOOLS_SCM_PRETEND_VERSION=$SWITCHBOT_MQTT_VERSION pipenv install --deploy --verbose

ENV PATH=$SOURCE_DIR_PATH/.venv/bin:$PATH
ENTRYPOINT ["tini", "--"]
CMD ["switchbot-mqtt"]

#RUN apk add bluez-deprecated `# hcitool`
