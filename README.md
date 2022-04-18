# SwitchBot MQTT client

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![CI Pipeline Status](https://github.com/fphammerle/switchbot-mqtt/workflows/tests/badge.svg)](https://github.com/fphammerle/switchbot-mqtt/actions)
[![Coverage Status](https://coveralls.io/repos/github/fphammerle/switchbot-mqtt/badge.svg?branch=master)](https://coveralls.io/github/fphammerle/switchbot-mqtt?branch=master)
[![Last Release](https://img.shields.io/pypi/v/switchbot-mqtt.svg)](https://pypi.org/project/switchbot-mqtt/#history)
[![Compatible Python Versions](https://img.shields.io/pypi/pyversions/switchbot-mqtt.svg)](https://pypi.org/project/switchbot-mqtt/)

MQTT client controlling [SwitchBot button automators](https://www.switch-bot.com/bot)
and [curtain motors](https://www.switch-bot.com/products/switchbot-curtain)

Compatible with [Home Assistant](https://www.home-assistant.io/)'s
[MQTT Switch](https://www.home-assistant.io/integrations/switch.mqtt/)
and [MQTT Cover](https://www.home-assistant.io/integrations/cover.mqtt/) platform.

## Setup

```sh
$ pip3 install --user --upgrade switchbot-mqtt
```

## Usage

```sh
$ switchbot-mqtt --mqtt-host HOSTNAME_OR_IP_ADDRESS --mqtt-enable-tls
# or
$ switchbot-mqtt --mqtt-host HOSTNAME_OR_IP_ADDRESS --mqtt-disable-tls
```

Use `sudo hcitool lescan`
or select device settings > 3 dots on top right in
[SwitchBot app](https://play.google.com/store/apps/details?id=com.theswitchbot.switchbot)
to determine your SwitchBot's **mac address**.

### Button Automator

Send `ON` or `OFF` to topic `homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set`.

```sh
$ mosquitto_pub -h MQTT_BROKER -t homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set -m ON
```

The command-line option `--fetch-device-info` enables battery level reports on topic
`homeassistant/switch/switchbot/MAC_ADDRESS/battery-percentage` after every command.
The report may be requested manually by sending a MQTT message to the topic
`homeassistant/switch/switchbot/MAC_ADDRESS/request-device-info` (requires `--fetch-device-info`)

### Curtain Motor

Send `OPEN`, `CLOSE`, or `STOP` to topic `homeassistant/cover/switchbot-curtain/aa:bb:cc:dd:ee:ff/set`:

```sh
$ mosquitto_pub -h MQTT_BROKER -t homeassistant/cover/switchbot-curtain/aa:bb:cc:dd:ee:ff/set -m CLOSE
```

Or a position in percent (0 fully closed, 100 fully opened) to topic
`homeassistant/cover/switchbot-curtain/aa:bb:cc:dd:ee:ff/position/set-percent`:

```sh
$ mosquitto_pub -h MQTT_BROKER -t homeassistant/cover/switchbot-curtain/aa:bb:cc:dd:ee:ff/position/set-percent -m 42
```

The command-line option `--fetch-device-info` enables position reports on topic
`homeassistant/cover/switchbot-curtain/MAC_ADDRESS/position` after `STOP` commands
and battery level reports on topic `homeassistant/cover/switchbot-curtain/MAC_ADDRESS/battery-percentage`
after every command.
These reports may be requested manually by sending a MQTT message to the topic
`homeassistant/cover/switchbot-curtain/MAC_ADDRESS/request-device-info` (requires `--fetch-device-info`)

### Device Passwords

In case some of your Switchbot devices are password-protected,
create a JSON file mapping MAC addresses to passwords
and provide its path via the `--device-password-file` option:
```json
{
  "11:22:33:44:55:66": "password",
  "aa:bb:cc:dd:ee:ff": "secret",
  "00:00:00:0f:f1:ce": "random string"
}
```
```sh
$ switchbot-mqtt --device-password-file /some/where/switchbot-passwords.json …
```

### MQTT Authentication

```sh
switchbot-mqtt --mqtt-username me --mqtt-password secret …
# or
switchbot-mqtt --mqtt-username me --mqtt-password-file /var/lib/secrets/mqtt/password …
```

⚠️  `--mqtt-password` leaks the password to other users on the same machine,
if `/proc` is mounted with `hidepid=0` (default).

### MQTT Topic

By default, `switchbot-mqtt` prepends `homeassistant/` to all MQTT topics.
This common prefix can be changed via `--mqtt-topic-prefix`:
```sh
# listens on living-room/switch/switchbot/aa:bb:cc:dd:ee:ff/set
switchbot-mqtt --mqtt-topic-prefix living-room/ …
# listens on switch/switchbot/aa:bb:cc:dd:ee:ff/set
switchbot-mqtt --mqtt-topic-prefix '' …
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
  name: switchbot_button
  command_topic: homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set
  state_topic: homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/state
  # http://materialdesignicons.com/
  icon: mdi:light-switch

cover:
- platform: mqtt
  name: switchbot_curtains
  command_topic: homeassistant/cover/switchbot-curtain/11:22:33:44:55:66/set
  set_position_topic: homeassistant/cover/switchbot-curtain/aa:bb:cc:dd:ee:ff/position/set-percent
  state_topic: homeassistant/cover/switchbot-curtain/11:22:33:44:55:66/state
```

## Docker 🐳

Pre-built docker images are available at https://hub.docker.com/r/fphammerle/switchbot-mqtt/tags

Annotation of signed tags `docker/*` contains docker image digests: https://github.com/fphammerle/switchbot-mqtt/tags

```sh
$ docker build -t switchbot-mqtt .
$ docker run --name spelunca_switchbot \
    --userns host --network host \
    switchbot-mqtt:latest \
    switchbot-mqtt --mqtt-host HOSTNAME_OR_IP_ADDRESS
```

Alternatively, you can use `docker-compose`:
```yaml
version: '3.8'

services:
  switchbot-mqtt:
    image: switchbot-mqtt
    container_name: switchbot-mqtt
    network_mode: host
    userns_mode: host
    environment:
    - MQTT_HOST=localhost
    - MQTT_PORT=1883
    #- MQTT_USERNAME=username
    #- MQTT_PASSWORD=password
    #- FETCH_DEVICE_INFO=yes
    restart: unless-stopped
```

## Alternatives

* https://github.com/binsentsu/switchbot-ctrl
* https://github.com/OpenWonderLabs/python-host/blob/master/switchbot_py3.py
* https://gist.github.com/aerialist/163a5794e95ccd28dc023161324009ed
* https://gist.github.com/mugifly/a29f34df7de8960d72245fcb124513c7
