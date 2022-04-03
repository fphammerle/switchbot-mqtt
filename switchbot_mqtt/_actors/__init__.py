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

import logging
import typing

import bluepy.btle
import paho.mqtt.client
import switchbot

from switchbot_mqtt._actors.base import _MQTTCallbackUserdata, _MQTTControlledActor
from switchbot_mqtt._utils import (
    _join_mqtt_topic_levels,
    _MQTTTopicLevel,
    _MQTTTopicPlaceholder,
)

_LOGGER = logging.getLogger(__name__)

_BUTTON_TOPIC_LEVELS_PREFIX = (
    "switch",
    "switchbot",
    _MQTTTopicPlaceholder.MAC_ADDRESS,
)
_CURTAIN_TOPIC_LEVELS_PREFIX = (
    "cover",
    "switchbot-curtain",
    _MQTTTopicPlaceholder.MAC_ADDRESS,
)


class _ButtonAutomator(_MQTTControlledActor):
    # https://www.home-assistant.io/integrations/switch.mqtt/

    MQTT_COMMAND_TOPIC_LEVELS = _BUTTON_TOPIC_LEVELS_PREFIX + ("set",)
    _MQTT_UPDATE_DEVICE_INFO_TOPIC_LEVELS = _BUTTON_TOPIC_LEVELS_PREFIX + (
        "request-device-info",
    )
    MQTT_STATE_TOPIC_LEVELS = _BUTTON_TOPIC_LEVELS_PREFIX + ("state",)
    _MQTT_BATTERY_PERCENTAGE_TOPIC_LEVELS = _BUTTON_TOPIC_LEVELS_PREFIX + (
        "battery-percentage",
    )

    def __init__(
        self, *, mac_address: str, retry_count: int, password: typing.Optional[str]
    ) -> None:
        self.__device = switchbot.Switchbot(
            mac=mac_address, password=password, retry_count=retry_count
        )
        super().__init__(
            mac_address=mac_address, retry_count=retry_count, password=password
        )

    def _get_device(self) -> switchbot.SwitchbotDevice:
        return self.__device

    def execute_command(
        self,
        *,
        mqtt_message_payload: bytes,
        mqtt_client: paho.mqtt.client.Client,
        update_device_info: bool,
        mqtt_topic_prefix: str,
    ) -> None:
        # https://www.home-assistant.io/integrations/switch.mqtt/#payload_on
        if mqtt_message_payload.lower() == b"on":
            if not self.__device.turn_on():
                _LOGGER.error("failed to turn on switchbot %s", self._mac_address)
            else:
                _LOGGER.info("switchbot %s turned on", self._mac_address)
                # https://www.home-assistant.io/integrations/switch.mqtt/#state_on
                self.report_state(
                    mqtt_client=mqtt_client,
                    mqtt_topic_prefix=mqtt_topic_prefix,
                    state=b"ON",
                )
                if update_device_info:
                    self._update_and_report_device_info(mqtt_client, mqtt_topic_prefix)
        # https://www.home-assistant.io/integrations/switch.mqtt/#payload_off
        elif mqtt_message_payload.lower() == b"off":
            if not self.__device.turn_off():
                _LOGGER.error("failed to turn off switchbot %s", self._mac_address)
            else:
                _LOGGER.info("switchbot %s turned off", self._mac_address)
                self.report_state(
                    mqtt_client=mqtt_client,
                    mqtt_topic_prefix=mqtt_topic_prefix,
                    state=b"OFF",
                )
                if update_device_info:
                    self._update_and_report_device_info(mqtt_client, mqtt_topic_prefix)
        else:
            _LOGGER.warning(
                "unexpected payload %r (expected 'ON' or 'OFF')", mqtt_message_payload
            )


class _CurtainMotor(_MQTTControlledActor):

    # https://www.home-assistant.io/integrations/cover.mqtt/
    MQTT_COMMAND_TOPIC_LEVELS = _CURTAIN_TOPIC_LEVELS_PREFIX + ("set",)
    _MQTT_SET_POSITION_TOPIC_LEVELS: typing.Tuple[
        _MQTTTopicLevel, ...
    ] = _CURTAIN_TOPIC_LEVELS_PREFIX + (
        "position",
        "set-percent",
    )
    _MQTT_UPDATE_DEVICE_INFO_TOPIC_LEVELS = _CURTAIN_TOPIC_LEVELS_PREFIX + (
        "request-device-info",
    )
    MQTT_STATE_TOPIC_LEVELS = _CURTAIN_TOPIC_LEVELS_PREFIX + ("state",)
    _MQTT_BATTERY_PERCENTAGE_TOPIC_LEVELS = _CURTAIN_TOPIC_LEVELS_PREFIX + (
        "battery-percentage",
    )
    _MQTT_POSITION_TOPIC_LEVELS = _CURTAIN_TOPIC_LEVELS_PREFIX + ("position",)

    @classmethod
    def get_mqtt_position_topic(cls, prefix: str, mac_address: str) -> str:
        return _join_mqtt_topic_levels(
            topic_prefix=prefix,
            topic_levels=cls._MQTT_POSITION_TOPIC_LEVELS,
            mac_address=mac_address,
        )

    def __init__(
        self, *, mac_address: str, retry_count: int, password: typing.Optional[str]
    ) -> None:
        # > The position of the curtain is saved in self._pos with 0 = open and 100 = closed.
        # https://github.com/Danielhiversen/pySwitchbot/blob/0.10.0/switchbot/__init__.py#L150
        self.__device = switchbot.SwitchbotCurtain(
            mac=mac_address,
            password=password,
            retry_count=retry_count,
            reverse_mode=True,
        )
        super().__init__(
            mac_address=mac_address, retry_count=retry_count, password=password
        )

    def _get_device(self) -> switchbot.SwitchbotDevice:
        return self.__device

    def _report_position(
        self,
        mqtt_client: paho.mqtt.client.Client,
        mqtt_topic_prefix: str,
    ) -> None:
        # > position_closed integer (Optional, default: 0)
        # > position_open integer (Optional, default: 100)
        # https://www.home-assistant.io/integrations/cover.mqtt/#position_closed
        # SwitchbotCurtain.get_position() returns a cached value within [0, 100].
        # SwitchbotCurtain.open() and .close() update the position optimistically,
        # SwitchbotCurtain.update() fetches the real position via bluetooth.
        # https://github.com/Danielhiversen/pySwitchbot/blob/0.10.0/switchbot/__init__.py#L202
        self._mqtt_publish(
            topic_prefix=mqtt_topic_prefix,
            topic_levels=self._MQTT_POSITION_TOPIC_LEVELS,
            payload=str(int(self.__device.get_position())).encode(),
            mqtt_client=mqtt_client,
        )

    def _update_and_report_device_info(  # pylint: disable=arguments-differ; report_position is optional
        self,
        mqtt_client: paho.mqtt.client.Client,
        mqtt_topic_prefix: str,
        *,
        report_position: bool = True,
    ) -> None:
        super()._update_and_report_device_info(mqtt_client, mqtt_topic_prefix)
        if report_position:
            self._report_position(
                mqtt_client=mqtt_client, mqtt_topic_prefix=mqtt_topic_prefix
            )

    def execute_command(
        self,
        *,
        mqtt_message_payload: bytes,
        mqtt_client: paho.mqtt.client.Client,
        update_device_info: bool,
        mqtt_topic_prefix: str,
    ) -> None:
        # https://www.home-assistant.io/integrations/cover.mqtt/#payload_open
        report_device_info, report_position = False, False
        if mqtt_message_payload.lower() == b"open":
            if not self.__device.open():
                _LOGGER.error("failed to open switchbot curtain %s", self._mac_address)
            else:
                _LOGGER.info("switchbot curtain %s opening", self._mac_address)
                # > state_opening string (Optional, default: opening)
                # https://www.home-assistant.io/integrations/cover.mqtt/#state_opening
                self.report_state(
                    mqtt_client=mqtt_client,
                    mqtt_topic_prefix=mqtt_topic_prefix,
                    state=b"opening",
                )
                report_device_info = update_device_info
        elif mqtt_message_payload.lower() == b"close":
            if not self.__device.close():
                _LOGGER.error("failed to close switchbot curtain %s", self._mac_address)
            else:
                _LOGGER.info("switchbot curtain %s closing", self._mac_address)
                # https://www.home-assistant.io/integrations/cover.mqtt/#state_closing
                self.report_state(
                    mqtt_client=mqtt_client,
                    mqtt_topic_prefix=mqtt_topic_prefix,
                    state=b"closing",
                )
                report_device_info = update_device_info
        elif mqtt_message_payload.lower() == b"stop":
            if not self.__device.stop():
                _LOGGER.error("failed to stop switchbot curtain %s", self._mac_address)
            else:
                _LOGGER.info("switchbot curtain %s stopped", self._mac_address)
                # no "stopped" state mentioned at
                # https://www.home-assistant.io/integrations/cover.mqtt/#configuration-variables
                # https://community.home-assistant.io/t/mqtt-how-to-remove-retained-messages/79029/2
                self.report_state(
                    mqtt_client=mqtt_client,
                    mqtt_topic_prefix=mqtt_topic_prefix,
                    state=b"",
                )
                report_device_info = update_device_info
                report_position = True
        else:
            _LOGGER.warning(
                "unexpected payload %r (expected 'OPEN', 'CLOSE', or 'STOP')",
                mqtt_message_payload,
            )
        if report_device_info:
            self._update_and_report_device_info(
                mqtt_client=mqtt_client,
                mqtt_topic_prefix=mqtt_topic_prefix,
                report_position=report_position,
            )

    @classmethod
    def _mqtt_set_position_callback(
        cls,
        mqtt_client: paho.mqtt.client.Client,
        userdata: _MQTTCallbackUserdata,
        message: paho.mqtt.client.MQTTMessage,
    ) -> None:
        # pylint: disable=unused-argument; callback
        # https://github.com/eclipse/paho.mqtt.python/blob/v1.6.1/src/paho/mqtt/client.py#L3556
        _LOGGER.debug("received topic=%s payload=%r", message.topic, message.payload)
        if message.retain:
            _LOGGER.info("ignoring retained message on topic %s", message.topic)
            return
        actor = cls._init_from_topic(
            topic=message.topic,
            expected_topic_levels=cls._MQTT_SET_POSITION_TOPIC_LEVELS,
            settings=userdata,
        )
        if not actor:
            return  # warning in _init_from_topic
        position_percent = int(message.payload.decode(), 10)
        if position_percent < 0 or position_percent > 100:
            _LOGGER.warning("invalid position %u%%, ignoring message", position_percent)
            return
        # pylint: disable=protected-access; own instance
        if actor._get_device().set_position(position_percent):
            _LOGGER.info(
                "set position of switchbot curtain %s to %u%%",
                actor._mac_address,
                position_percent,
            )
        else:
            _LOGGER.error(
                "failed to set position of switchbot curtain %s", actor._mac_address
            )

    @classmethod
    def _get_mqtt_message_callbacks(
        cls,
        *,
        enable_device_info_update_topic: bool,
    ) -> typing.Dict[typing.Tuple[_MQTTTopicLevel, ...], typing.Callable]:
        callbacks = super()._get_mqtt_message_callbacks(
            enable_device_info_update_topic=enable_device_info_update_topic
        )
        callbacks[cls._MQTT_SET_POSITION_TOPIC_LEVELS] = cls._mqtt_set_position_callback
        return callbacks
