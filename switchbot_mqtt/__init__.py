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
import enum
import logging
import pathlib
import re
import typing

import paho.mqtt.client
import switchbot

_LOGGER = logging.getLogger(__name__)


class _SwitchbotAction(enum.Enum):
    ON = 1
    OFF = 2


class _SwitchbotState(enum.Enum):
    ON = 1
    OFF = 2


# https://www.home-assistant.io/docs/mqtt/discovery/#switches
_MQTT_TOPIC_PREFIX_LEVELS = ["homeassistant", "switch", "switchbot"]
_MQTT_TOPIC_MAC_ADDRESS_PLACEHOLDER = "{mac_address}"
_MQTT_SET_TOPIC_LEVELS = _MQTT_TOPIC_PREFIX_LEVELS + [
    _MQTT_TOPIC_MAC_ADDRESS_PLACEHOLDER,
    "set",
]
_MQTT_SET_TOPIC = "/".join(_MQTT_SET_TOPIC_LEVELS).replace(
    _MQTT_TOPIC_MAC_ADDRESS_PLACEHOLDER, "+"
)
_MQTT_STATE_TOPIC = "/".join(
    _MQTT_TOPIC_PREFIX_LEVELS + [_MQTT_TOPIC_MAC_ADDRESS_PLACEHOLDER, "state"]
)
# https://www.home-assistant.io/integrations/switch.mqtt/#state_off
_MQTT_STATE_PAYLOAD_MAPPING = {_SwitchbotState.ON: b"ON", _SwitchbotState.OFF: b"OFF"}
_MAC_ADDRESS_REGEX = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")


def _mac_address_valid(mac_address: str) -> bool:
    return _MAC_ADDRESS_REGEX.match(mac_address.lower()) is not None


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


def _report_state(
    mqtt_client: paho.mqtt.client.Client,
    switchbot_mac_address: str,
    switchbot_state: _SwitchbotState,
) -> None:
    # https://pypi.org/project/paho-mqtt/#publishing
    topic = _MQTT_STATE_TOPIC.replace(
        _MQTT_TOPIC_MAC_ADDRESS_PLACEHOLDER, switchbot_mac_address
    )
    payload = _MQTT_STATE_PAYLOAD_MAPPING[switchbot_state]
    _LOGGER.debug("publishing topic=%s payload=%r", topic, payload)
    message_info = mqtt_client.publish(
        topic=topic, payload=payload, retain=True
    )  # type: paho.mqtt.client.MQTTMessageInfo
    if message_info.rc != paho.mqtt.client.MQTT_ERR_SUCCESS:
        _LOGGER.error("failed to publish state (rc=%d)", message_info.rc)


def _send_command(
    mqtt_client: paho.mqtt.client.Client,
    switchbot_mac_address: str,
    action: _SwitchbotAction,
) -> None:
    switchbot_device = switchbot.Switchbot(mac=switchbot_mac_address)
    if action == _SwitchbotAction.ON:
        if not switchbot_device.turn_on():
            _LOGGER.error("failed to turn on switchbot %s", switchbot_mac_address)
        else:
            _LOGGER.info("switchbot %s turned on", switchbot_mac_address)
            _report_state(
                mqtt_client=mqtt_client,
                switchbot_mac_address=switchbot_mac_address,
                switchbot_state=_SwitchbotState.ON,
            )
    else:
        assert action == _SwitchbotAction.OFF, action
        if not switchbot_device.turn_off():
            _LOGGER.error("failed to turn off switchbot %s", switchbot_mac_address)
        else:
            _LOGGER.info("switchbot %s turned off", switchbot_mac_address)
            _report_state(
                mqtt_client=mqtt_client,
                switchbot_mac_address=switchbot_mac_address,
                switchbot_state=_SwitchbotState.OFF,
            )


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
    if len(topic_split) != len(_MQTT_SET_TOPIC_LEVELS):
        _LOGGER.warning("unexpected topic %s", message.topic)
        return
    switchbot_mac_address = None
    for given_part, expected_part in zip(topic_split, _MQTT_SET_TOPIC_LEVELS):
        if expected_part == _MQTT_TOPIC_MAC_ADDRESS_PLACEHOLDER:
            switchbot_mac_address = given_part
        elif expected_part != given_part:
            _LOGGER.warning("unexpected topic %s", message.topic)
            return
    assert switchbot_mac_address
    if not _mac_address_valid(switchbot_mac_address):
        _LOGGER.warning("invalid mac address %s", switchbot_mac_address)
        return
    # https://www.home-assistant.io/integrations/switch.mqtt/#payload_off
    if message.payload.lower() == b"on":
        action = _SwitchbotAction.ON
    elif message.payload.lower() == b"off":
        action = _SwitchbotAction.OFF
    else:
        _LOGGER.warning("unexpected payload %r", message.payload)
        return
    _send_command(
        mqtt_client=mqtt_client,
        switchbot_mac_address=switchbot_mac_address,
        action=action,
    )


def _run(
    mqtt_host: str,
    mqtt_port: int,
    mqtt_username: typing.Optional[str],
    mqtt_password: typing.Optional[str],
) -> None:
    # https://pypi.org/project/paho-mqtt/
    mqtt_client = paho.mqtt.client.Client()
    mqtt_client.on_connect = _mqtt_on_connect
    mqtt_client.on_message = _mqtt_on_message
    _LOGGER.info("connecting to MQTT broker %s:%d", mqtt_host, mqtt_port)
    if mqtt_username:
        mqtt_client.username_pw_set(username=mqtt_username, password=mqtt_password)
    elif mqtt_password:
        raise ValueError("Missing MQTT username")
    mqtt_client.connect(host=mqtt_host, port=mqtt_port)
    mqtt_client.loop_forever()


def _main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s:%(levelname)s:%(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    argparser = argparse.ArgumentParser(
        description="MQTT client controlling SwitchBot button automators, "
        "compatible with home-assistant.io's MQTT Switch platform"
    )
    argparser.add_argument("--mqtt-host", type=str, required=True)
    argparser.add_argument("--mqtt-port", type=int, default=1883)
    argparser.add_argument("--mqtt-username", type=str)
    password_argument_group = argparser.add_mutually_exclusive_group()
    password_argument_group.add_argument("--mqtt-password", type=str)
    password_argument_group.add_argument(
        "--mqtt-password-file",
        type=pathlib.Path,
        metavar="PATH",
        dest="mqtt_password_path",
        help="stripping trailing newline",
    )
    args = argparser.parse_args()
    if args.mqtt_password_path:
        # .read_text() replaces \r\n with \n
        mqtt_password = args.mqtt_password_path.read_bytes().decode()
        if mqtt_password.endswith("\r\n"):
            mqtt_password = mqtt_password[:-2]
        elif mqtt_password.endswith("\n"):
            mqtt_password = mqtt_password[:-1]
    else:
        mqtt_password = args.mqtt_password
    _run(
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
        mqtt_username=args.mqtt_username,
        mqtt_password=mqtt_password,
    )
