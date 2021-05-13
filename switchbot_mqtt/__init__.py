# switchbot-mqtt - MQTT client controlling SwitchBot button & curtain automators,
# compatible with home-assistant.io's MQTT Switch & Cover platform
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

import abc
import argparse
import enum
import logging
import pathlib
import re
import typing

import paho.mqtt.client
import switchbot

_LOGGER = logging.getLogger(__name__)

_MAC_ADDRESS_REGEX = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")


class _MQTTTopicPlaceholder(enum.Enum):
    MAC_ADDRESS = "MAC_ADDRESS"


_MQTTTopicLevel = typing.Union[str, _MQTTTopicPlaceholder]
# "homeassistant" for historic reason, may be parametrized in future
_MQTT_TOPIC_LEVELS_PREFIX = ["homeassistant"]  # type: typing.List[_MQTTTopicLevel]


def _mac_address_valid(mac_address: str) -> bool:
    return _MAC_ADDRESS_REGEX.match(mac_address.lower()) is not None


class _MQTTControlledActor(abc.ABC):
    MQTT_COMMAND_TOPIC_LEVELS = NotImplemented  # type: typing.List[_MQTTTopicLevel]
    MQTT_STATE_TOPIC_LEVELS = NotImplemented  # type: typing.List[_MQTTTopicLevel]

    def __init__(self, mac_address: str) -> None:
        # alternative: pySwitchbot >=0.10.0 provides SwitchbotDevice.get_mac()
        self._mac_address = mac_address

    @abc.abstractmethod
    def execute_command(
        self, mqtt_message_payload: bytes, mqtt_client: paho.mqtt.client.Client
    ) -> None:
        raise NotImplementedError()

    @classmethod
    def _mqtt_command_callback(
        cls,
        mqtt_client: paho.mqtt.client.Client,
        userdata: None,
        message: paho.mqtt.client.MQTTMessage,
    ) -> None:
        # pylint: disable=unused-argument; callback
        # https://github.com/eclipse/paho.mqtt.python/blob/v1.5.0/src/paho/mqtt/client.py#L469
        _LOGGER.debug("received topic=%s payload=%r", message.topic, message.payload)
        if message.retain:
            _LOGGER.info("ignoring retained message")
            return
        topic_split = message.topic.split("/")
        if len(topic_split) != len(cls.MQTT_COMMAND_TOPIC_LEVELS):
            _LOGGER.warning("unexpected topic %s", message.topic)
            return
        mac_address = None
        for given_part, expected_part in zip(
            topic_split, cls.MQTT_COMMAND_TOPIC_LEVELS
        ):
            if expected_part == _MQTTTopicPlaceholder.MAC_ADDRESS:
                mac_address = given_part
            elif expected_part != given_part:
                _LOGGER.warning("unexpected topic %s", message.topic)
                return
        assert mac_address
        if not _mac_address_valid(mac_address):
            _LOGGER.warning("invalid mac address %s", mac_address)
            return
        cls(mac_address=mac_address).execute_command(
            mqtt_message_payload=message.payload, mqtt_client=mqtt_client
        )

    @classmethod
    def mqtt_subscribe(cls, mqtt_client: paho.mqtt.client.Client) -> None:
        command_topic = "/".join(
            "+" if isinstance(l, _MQTTTopicPlaceholder) else l
            for l in cls.MQTT_COMMAND_TOPIC_LEVELS
        )
        _LOGGER.info("subscribing to MQTT topic %r", command_topic)
        mqtt_client.subscribe(command_topic)
        mqtt_client.message_callback_add(
            sub=command_topic, callback=cls._mqtt_command_callback
        )

    def _mqtt_publish(
        self,
        topic_levels: typing.List[_MQTTTopicLevel],
        payload: bytes,
        mqtt_client: paho.mqtt.client.Client,
    ) -> None:
        topic = "/".join(
            self._mac_address
            if l == _MQTTTopicPlaceholder.MAC_ADDRESS
            else typing.cast(str, l)
            for l in topic_levels
        )
        # https://pypi.org/project/paho-mqtt/#publishing
        _LOGGER.debug("publishing topic=%s payload=%r", topic, payload)
        message_info = mqtt_client.publish(
            topic=topic, payload=payload, retain=True
        )  # type: paho.mqtt.client.MQTTMessageInfo
        # wait before checking status?
        if message_info.rc != paho.mqtt.client.MQTT_ERR_SUCCESS:
            _LOGGER.error(
                "Failed to publish MQTT message on topic %s (rc=%d)",
                topic,
                message_info.rc,
            )

    def report_state(self, state: bytes, mqtt_client: paho.mqtt.client.Client) -> None:
        self._mqtt_publish(
            topic_levels=self.MQTT_STATE_TOPIC_LEVELS,
            payload=state,
            mqtt_client=mqtt_client,
        )


class _ButtonAutomator(_MQTTControlledActor):
    # https://www.home-assistant.io/integrations/switch.mqtt/

    MQTT_COMMAND_TOPIC_LEVELS = _MQTT_TOPIC_LEVELS_PREFIX + [
        "switch",
        "switchbot",
        _MQTTTopicPlaceholder.MAC_ADDRESS,
        "set",
    ]

    MQTT_STATE_TOPIC_LEVELS = _MQTT_TOPIC_LEVELS_PREFIX + [
        "switch",
        "switchbot",
        _MQTTTopicPlaceholder.MAC_ADDRESS,
        "state",
    ]

    def __init__(self, mac_address) -> None:
        self._device = switchbot.Switchbot(mac=mac_address)
        super().__init__(mac_address=mac_address)

    def execute_command(
        self, mqtt_message_payload: bytes, mqtt_client: paho.mqtt.client.Client
    ) -> None:
        # https://www.home-assistant.io/integrations/switch.mqtt/#payload_on
        if mqtt_message_payload.lower() == b"on":
            if not self._device.turn_on():
                _LOGGER.error("failed to turn on switchbot %s", self._mac_address)
            else:
                _LOGGER.info("switchbot %s turned on", self._mac_address)
                # https://www.home-assistant.io/integrations/switch.mqtt/#state_on
                self.report_state(mqtt_client=mqtt_client, state=b"ON")
        # https://www.home-assistant.io/integrations/switch.mqtt/#payload_off
        elif mqtt_message_payload.lower() == b"off":
            if not self._device.turn_off():
                _LOGGER.error("failed to turn off switchbot %s", self._mac_address)
            else:
                _LOGGER.info("switchbot %s turned off", self._mac_address)
                self.report_state(mqtt_client=mqtt_client, state=b"OFF")
        else:
            _LOGGER.warning(
                "unexpected payload %r (expected 'ON' or 'OFF')", mqtt_message_payload
            )


class _CurtainMotor(_MQTTControlledActor):
    # https://www.home-assistant.io/integrations/cover.mqtt/

    MQTT_COMMAND_TOPIC_LEVELS = _MQTT_TOPIC_LEVELS_PREFIX + [
        "cover",
        "switchbot-curtain",
        _MQTTTopicPlaceholder.MAC_ADDRESS,
        "set",
    ]

    MQTT_STATE_TOPIC_LEVELS = _MQTT_TOPIC_LEVELS_PREFIX + [
        "cover",
        "switchbot-curtain",
        _MQTTTopicPlaceholder.MAC_ADDRESS,
        "state",
    ]

    _MQTT_POSITION_TOPIC_LEVELS = _MQTT_TOPIC_LEVELS_PREFIX + [
        "cover",
        "switchbot-curtain",
        _MQTTTopicPlaceholder.MAC_ADDRESS,
        "position",
    ]

    def __init__(self, mac_address) -> None:
        # > The position of the curtain is saved in self._pos with 0 = open and 100 = closed.
        # https://github.com/Danielhiversen/pySwitchbot/blob/0.10.0/switchbot/__init__.py#L150
        self._device = switchbot.SwitchbotCurtain(mac=mac_address, reverse_mode=True)
        super().__init__(mac_address=mac_address)

    def _report_position(self, mqtt_client: paho.mqtt.client.Client) -> None:
        # > position_closed integer (Optional, default: 0)
        # > position_open integer (Optional, default: 100)
        # https://www.home-assistant.io/integrations/cover.mqtt/#position_closed
        # SwitchbotCurtain.get_position() returns a cached value within [0, 100].
        # SwitchbotCurtain.open() and .close() update the position optimistically,
        # SwitchbotCurtain.update() fetches the real position via bluetooth.
        # https://github.com/Danielhiversen/pySwitchbot/blob/0.10.0/switchbot/__init__.py#L202
        self._mqtt_publish(
            topic_levels=self._MQTT_POSITION_TOPIC_LEVELS,
            payload=str(int(self._device.get_position())).encode(),
            mqtt_client=mqtt_client,
        )

    def _update_position(self, mqtt_client: paho.mqtt.client.Client) -> None:
        self._device.update()
        self._report_position(mqtt_client=mqtt_client)

    def execute_command(
        self, mqtt_message_payload: bytes, mqtt_client: paho.mqtt.client.Client
    ) -> None:
        # https://www.home-assistant.io/integrations/cover.mqtt/#payload_open
        if mqtt_message_payload.lower() == b"open":
            if not self._device.open():
                _LOGGER.error("failed to open switchbot curtain %s", self._mac_address)
            else:
                _LOGGER.info("switchbot curtain %s opening", self._mac_address)
                # > state_opening string (Optional, default: opening)
                # https://www.home-assistant.io/integrations/cover.mqtt/#state_opening
                self.report_state(mqtt_client=mqtt_client, state=b"opening")
        elif mqtt_message_payload.lower() == b"close":
            if not self._device.close():
                _LOGGER.error("failed to close switchbot curtain %s", self._mac_address)
            else:
                _LOGGER.info("switchbot curtain %s closing", self._mac_address)
                # https://www.home-assistant.io/integrations/cover.mqtt/#state_closing
                self.report_state(mqtt_client=mqtt_client, state=b"closing")
        elif mqtt_message_payload.lower() == b"stop":
            if not self._device.stop():
                _LOGGER.error("failed to stop switchbot curtain %s", self._mac_address)
            else:
                _LOGGER.info("switchbot curtain %s stopped", self._mac_address)
                # no "stopped" state mentioned at
                # https://www.home-assistant.io/integrations/cover.mqtt/#configuration-variables
                # https://community.home-assistant.io/t/mqtt-how-to-remove-retained-messages/79029/2
                self.report_state(mqtt_client=mqtt_client, state=b"")
                self._update_position(mqtt_client=mqtt_client)
        else:
            _LOGGER.warning(
                "unexpected payload %r (expected 'OPEN', 'CLOSE', or 'STOP')",
                mqtt_message_payload,
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
    _ButtonAutomator.mqtt_subscribe(mqtt_client=mqtt_client)
    _CurtainMotor.mqtt_subscribe(mqtt_client=mqtt_client)


def _run(
    mqtt_host: str,
    mqtt_port: int,
    mqtt_username: typing.Optional[str],
    mqtt_password: typing.Optional[str],
) -> None:
    # https://pypi.org/project/paho-mqtt/
    mqtt_client = paho.mqtt.client.Client()
    mqtt_client.on_connect = _mqtt_on_connect
    _LOGGER.info("connecting to MQTT broker %s:%d", mqtt_host, mqtt_port)
    if mqtt_username:
        mqtt_client.username_pw_set(username=mqtt_username, password=mqtt_password)
    elif mqtt_password:
        raise ValueError("Missing MQTT username")
    mqtt_client.connect(host=mqtt_host, port=mqtt_port)
    # https://github.com/eclipse/paho.mqtt.python/blob/master/src/paho/mqtt/client.py#L1740
    mqtt_client.loop_forever()


def _main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
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
