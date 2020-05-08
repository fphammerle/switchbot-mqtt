# not using python:3.*-alpine cause glib-dev package depends on python3
# https://pkgs.alpinelinux.org/package/v3.11/main/aarch64/glib-dev
FROM alpine:3.11

RUN apk add --no-cache \
    gcc \
    glib-dev \
    make \
    musl-dev \
    tini
# TODO merge
RUN apk add --no-cache py3-virtualenv

#RUN apk add bluez-deprecated `# hcitool`

USER nobody

ARG SOURCE_DIR_PATH=/switchbot-mqtt
ARG SWITCHBOT_MQTT_VERSION=
COPY --chown=nobody . $SOURCE_DIR_PATH
WORKDIR $SOURCE_DIR_PATH
RUN virtualenv --no-site-packages .venv \
    && source .venv/bin/activate \
    && pip install --no-cache-dir pipenv \
    && SETUPTOOLS_SCM_PRETEND_VERSION=$SWITCHBOT_MQTT_VERSION pipenv install --deploy --verbose \
    && pipenv clean --verbose

ENV PATH=$SOURCE_DIR_PATH/.venv/bin:$PATH
ENTRYPOINT ["tini", "--"]
CMD ["switchbot-mqtt"]
