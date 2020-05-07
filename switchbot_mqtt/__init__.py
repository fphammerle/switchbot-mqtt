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
import switchbot

_LOGGER = logging.getLogger(__name__)

_MQTT_TOPIC_MAC_ADDRESS_PLACEHOLDER = "{mac_address}"
_MQTT_SET_TOPIC_PATTERN = [
    "homeassistant",
    "switch",
    "switchbot",
    _MQTT_TOPIC_MAC_ADDRESS_PLACEHOLDER,
    "set",
]  # TODO parametrize
_MQTT_SET_TOPIC = "/".join(_MQTT_SET_TOPIC_PATTERN).replace(
    _MQTT_TOPIC_MAC_ADDRESS_PLACEHOLDER, "+"
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
    mqtt_client.subscribe(_MQTT_SET_TOPIC)


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
    topic_split = message.topic.split("/")
    if len(topic_split) != len(_MQTT_SET_TOPIC_PATTERN):
        _LOGGER.warning("unexpected topic %s", message.topic)
        return
    switchbot_mac_address = None
    for given_part, expected_part in zip(topic_split, _MQTT_SET_TOPIC_PATTERN):
        if expected_part == _MQTT_TOPIC_MAC_ADDRESS_PLACEHOLDER:
            switchbot_mac_address = given_part
        elif expected_part != given_part:
            _LOGGER.warning("unexpected topic %s", message.topic)
            return
    assert switchbot_mac_address
    # TODO validate mac address
    switchbot_device = switchbot.Switchbot(mac=switchbot_mac_address)
    if message.payload.lower() == b"on":
        print("TODO", switchbot_device.turn_on())
    elif message.payload.lower() == b"off":
        print("TODO", switchbot_device.turn_off())
    else:
        _LOGGER.warning("unexpected payload %r", message.payload)


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
