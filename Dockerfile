# sync with https://github.com/fphammerle/systemctl-mqtt/blob/master/Dockerfile

# not using python:3.*-alpine cause glib-dev package depends on python3
# https://pkgs.alpinelinux.org/package/v3.11/main/aarch64/glib-dev
ARG BASE_IMAGE=docker.io/alpine:3.13.1
ARG SOURCE_DIR_PATH=/switchbot-mqtt


# hadolint ignore=DL3006
FROM $BASE_IMAGE as build

RUN apk add --no-cache \
        gcc \
        git `# setuptools_scm` \
        glib-dev \
        jq `# edit Pipfile.lock` \
        make \
        musl-dev \
        py3-certifi `# pipenv` \
        py3-pip `# pipenv install` \
        py3-virtualenv `# pipenv` \
    && adduser -S build

USER build
RUN pip3 install --user --no-cache-dir pipenv==2021.5.29

ARG SOURCE_DIR_PATH
COPY --chown=build:nobody Pipfile Pipfile.lock $SOURCE_DIR_PATH/
WORKDIR $SOURCE_DIR_PATH
ENV PIPENV_CACHE_DIR=/tmp/pipenv-cache \
    PIPENV_VENV_IN_PROJECT=yes-please \
    PATH=/home/build/.local/bin:$PATH
# `sponge` is not pre-installed
RUN jq 'del(.default."switchbot-mqtt", .default."sanitized-package")' Pipfile.lock > Pipfile.lock~ \
    && mv Pipfile.lock~ Pipfile.lock \
    && pipenv install --deploy --verbose
COPY --chown=build:nobody . $SOURCE_DIR_PATH
RUN pipenv install --deploy --verbose \
    && pipenv graph \
    && pipenv run pip freeze \
    && rm -rf .git/ $PIPENV_CACHE_DIR \
    && chmod -cR a+rX .

# workaround for broken multi-stage copy
# > failed to copy files: failed to copy directory: Error processing tar file(exit status 1): Container ID ... cannot be mapped to a host ID
USER 0
RUN chown -R 0:0 $SOURCE_DIR_PATH
USER build


# hadolint ignore=DL3006
FROM $BASE_IMAGE

RUN apk add --no-cache \
        glib \
        python3 \
        tini \
    && find / -xdev -type f -perm /u+s -exec chmod -c u-s {} \; \
    && find / -xdev -type f -perm /g+s -exec chmod -c g-s {} \;
#RUN apk add bluez-deprecated `# hcitool`

USER nobody

ARG SOURCE_DIR_PATH
COPY --from=build $SOURCE_DIR_PATH $SOURCE_DIR_PATH
ARG VIRTUALENV_PATH=$SOURCE_DIR_PATH/.venv
ENV PATH=$VIRTUALENV_PATH/bin:$PATH

ENV MQTT_HOST ""
ENV MQTT_PORT "1883"
ENV MQTT_USERNAME ""
ENV MQTT_PASSWORD ""
ENTRYPOINT ["tini", "--"]
CMD ["sh", "-c", "switchbot-mqtt --mqtt-host \"$MQTT_HOST\" --mqtt-port \"$MQTT_PORT\" --mqtt-username \"$MQTT_USERNAME\" --mqtt-password \"$MQTT_PASSWORD\""]
