# switchbot-mqtt - MQTT client controlling SwitchBot button automators,
# compatible with home-assistant.io's MQTT Switch platform
#
# Copyright (C) 2020 Fabian Peter Hammerle <fabian@hammerle.me>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import argparse
import logging
import typing

import paho.mqtt.client

_LOGGER = logging.getLogger(__name__)

_MQTT_SET_TOPIC_PATTERN = (
    "homeassistant/switch/switchbot/{mac_address}/set"  # TODO parametrize
)


def _mqtt_on_connect(
    mqtt_client: paho.mqtt.client.Client,
    user_data: typing.Any,
    flags: typing.Dict,
    return_code: int,
) -> None:
    # pylint: disable=unused-argument; callback
    # https://github.com/eclipse/paho.mqtt.python/blob/v1.5.0/src/paho/mqtt/client.py#L441
    assert return_code == 0, return_code  # connection accepted
    mqtt_broker_host, mqtt_broker_port = mqtt_client.socket().getpeername()
    _LOGGER.debug("connected to MQTT broker %s:%d", mqtt_broker_host, mqtt_broker_port)
    # https://www.home-assistant.io/docs/mqtt/discovery/#discovery_prefix
    mqtt_client.subscribe(_MQTT_SET_TOPIC_PATTERN.format(mac_address="+"))


def _mqtt_on_message(
    mqtt_client: paho.mqtt.client.Client,
    user_data: typing.Any,
    message: paho.mqtt.client.MQTTMessage,
) -> None:
    # pylint: disable=unused-argument; callback
    # https://github.com/eclipse/paho.mqtt.python/blob/v1.5.0/src/paho/mqtt/client.py#L469
    _LOGGER.debug("received topic=%s payload=%r", message.topic, message.payload)
    if message.retain:
        _LOGGER.info("ignoring retained message")
        return
    print("TODO", message.topic, message.payload)


def _main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s:%(levelname)s:%(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    argparser = argparse.ArgumentParser(
        "MQTT client controlling SwitchBot button automators, "
        "compatible with home-assistant.io's MQTT Switch platform"
    )
    argparser.add_argument("--mqtt-host", type=str, required=True)
    argparser.add_argument("--mqtt-port", type=int, default=1883)
    args = argparser.parse_args()
    # https://pypi.org/project/paho-mqtt/
    mqtt_client = paho.mqtt.client.Client()
    mqtt_client.on_connect = _mqtt_on_connect
    mqtt_client.on_message = _mqtt_on_message
    _LOGGER.info(
        "connecting to MQTT broker %s:%d", args.mqtt_host, args.mqtt_port,
    )
    mqtt_client.connect(host=args.mqtt_host, port=args.mqtt_port)
    mqtt_client.loop_forever()
