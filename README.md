# SwitchBot MQTT client

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![CI Pipeline Status](https://github.com/fphammerle/switchbot-mqtt/workflows/tests/badge.svg)](https://github.com/fphammerle/switchbot-mqtt/actions)
[![Coverage Status](https://coveralls.io/repos/github/fphammerle/switchbot-mqtt/badge.svg?branch=master)](https://coveralls.io/github/fphammerle/switchbot-mqtt?branch=master)
[![Last Release](https://img.shields.io/pypi/v/switchbot-mqtt.svg)](https://pypi.org/project/switchbot-mqtt/#history)
[![Compatible Python Versions](https://img.shields.io/pypi/pyversions/switchbot-mqtt.svg)](https://pypi.org/project/switchbot-mqtt/)

MQTT client controlling [SwitchBot button automators](https://www.switch-bot.com/bot)

Compatible with [Home Assistant](https://www.home-assistant.io/)'s
[MQTT Switch](https://www.home-assistant.io/integrations/switch.mqtt/) platform.

## Setup

```sh
$ pip3 install --user --upgrade switchbot-mqtt
$ switchbot-mqtt --mqtt-host HOSTNAME_OR_IP_ADDRESS
```

Use `sudo hcitool lescan`
or select device settings > 3 dots on top right in
[SwitchBot app](https://play.google.com/store/apps/details?id=com.theswitchbot.switchbot)
to determine your SwitchBot's **mac address**.

Send `ON` or `OFF` to topic `homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set`.

```sh
$ mosquitto_pub -h MQTT_BROKER -t homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set -m ON
```

## Home Assistant 🏡

### Rationale

Why not use the official [SwitchBot integration](https://www.home-assistant.io/integrations/switchbot/)?

I prefer not to share the host's **network stack** with home assistant
(more complicated network setup
and additional [netfilter](https://en.wikipedia.org/wiki/Netfilter) rules required for isolation).

Sadly, `docker run --network host` even requires `--userns host`:
> docker: Error response from daemon: cannot share the host's network namespace when user namespaces are enabled.

The docker image built from this repository works around this limitation
by explicitly running as an **unprivileged user**.

The [official home assistant image](https://hub.docker.com/r/homeassistant/home-assistant)
runs as `root`.
This imposes an unnecessary security risk, especially when disabling user namespace remapping
(`--userns host`).
See https://github.com/fphammerle/docker-home-assistant for an alternative.

### Setup

```yaml
# https://www.home-assistant.io/docs/mqtt/broker/#configuration-variables
mqtt:
  broker: BROKER_HOSTNAME_OR_IP_ADDRESS
  # credentials, additional options…

# https://www.home-assistant.io/integrations/switch.mqtt/#configuration-variables
switch:
- platform: mqtt
  name: some_name
  command_topic: homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set
  state_topic: homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/state
  # http://materialdesignicons.com/
  icon: mdi:light-switch
```

## Docker 🐳

Pre-built docker image are available at https://hub.docker.com/r/fphammerle/switchbot-mqtt/tags

Annotation of signed tags `docker/*` contains docker image digests: https://github.com/fphammerle/switchbot-mqtt/tags

```sh
$ docker build -t switchbot-mqtt .
$ docker run --name spelunca_switchbot \
    --userns host --network host \
    switchbot-mqtt:latest \
    switchbot-mqtt --mqtt-host HOSTNAME_OR_IP_ADDRESS
```

## MQTT Authentication

```sh
switchbot-mqtt --mqtt-username me --mqtt-password secret …
# or
switchbot-mqtt --mqtt-username me --mqtt-password-file /var/lib/secrets/mqtt/password …
```

## Alternatives

* https://github.com/binsentsu/switchbot-ctrl
* https://github.com/OpenWonderLabs/python-host/blob/master/switchbot_py3.py
* https://gist.github.com/aerialist/163a5794e95ccd28dc023161324009ed
* https://gist.github.com/mugifly/a29f34df7de8960d72245fcb124513c7
