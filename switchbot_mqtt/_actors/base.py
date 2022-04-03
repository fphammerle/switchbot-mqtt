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

# > Even with __all__ set appropriately, internal interfaces (packages,
# > modules, classes, functions, attributes or other names) should still be
# > prefixed with a single leading underscore. An interface is also considered
# > internal if any containing namespace (package, module or class) is
# > considered internal.
# https://peps.python.org/pep-0008/#public-and-internal-interfaces

from __future__ import annotations  # PEP563 (default in python>=3.10)

import abc
import dataclasses
import logging
import queue
import shlex
import typing

import bluepy.btle
import paho.mqtt.client
import switchbot
from switchbot_mqtt._utils import (
    _join_mqtt_topic_levels,
    _mac_address_valid,
    _MQTTTopicLevel,
    _MQTTTopicPlaceholder,
    _parse_mqtt_topic,
    _QueueLogHandler,
)

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class _MQTTCallbackUserdata:
    retry_count: int
    device_passwords: typing.Dict[str, str]
    fetch_device_info: bool
    mqtt_topic_prefix: str


class _MQTTControlledActor(abc.ABC):
    MQTT_COMMAND_TOPIC_LEVELS: typing.Tuple[_MQTTTopicLevel, ...] = NotImplemented
    _MQTT_UPDATE_DEVICE_INFO_TOPIC_LEVELS: typing.Tuple[
        _MQTTTopicLevel, ...
    ] = NotImplemented
    MQTT_STATE_TOPIC_LEVELS: typing.Tuple[_MQTTTopicLevel, ...] = NotImplemented
    _MQTT_BATTERY_PERCENTAGE_TOPIC_LEVELS: typing.Tuple[
        _MQTTTopicLevel, ...
    ] = NotImplemented

    @classmethod
    def get_mqtt_update_device_info_topic(cls, *, prefix: str, mac_address: str) -> str:
        return _join_mqtt_topic_levels(
            topic_prefix=prefix,
            topic_levels=cls._MQTT_UPDATE_DEVICE_INFO_TOPIC_LEVELS,
            mac_address=mac_address,
        )

    @classmethod
    def get_mqtt_battery_percentage_topic(cls, *, prefix: str, mac_address: str) -> str:
        return _join_mqtt_topic_levels(
            topic_prefix=prefix,
            topic_levels=cls._MQTT_BATTERY_PERCENTAGE_TOPIC_LEVELS,
            mac_address=mac_address,
        )

    @abc.abstractmethod
    def __init__(
        self, *, mac_address: str, retry_count: int, password: typing.Optional[str]
    ) -> None:
        # alternative: pySwitchbot >=0.10.0 provides SwitchbotDevice.get_mac()
        self._mac_address = mac_address

    @abc.abstractmethod
    def _get_device(self) -> switchbot.SwitchbotDevice:
        raise NotImplementedError()

    def _update_device_info(self) -> None:
        log_queue: queue.Queue[logging.LogRecord] = queue.Queue(maxsize=0)
        logging.getLogger("switchbot").addHandler(_QueueLogHandler(log_queue))
        try:
            self._get_device().update()
            # pySwitchbot>=v0.10.1 catches bluepy.btle.BTLEManagementError :(
            # https://github.com/Danielhiversen/pySwitchbot/blob/0.10.1/switchbot/__init__.py#L141
            # pySwitchbot<0.11.0 WARNING, >=0.11.0 ERROR
            while not log_queue.empty():
                log_record = log_queue.get()
                if log_record.exc_info:
                    exc: typing.Optional[BaseException] = log_record.exc_info[1]
                    if (
                        isinstance(exc, bluepy.btle.BTLEManagementError)
                        and exc.emsg == "Permission Denied"
                    ):
                        raise exc
        except bluepy.btle.BTLEManagementError as exc:
            if (
                exc.emsg == "Permission Denied"
                and exc.message == "Failed to execute management command 'le on'"
            ):
                raise PermissionError(
                    "bluepy-helper failed to enable low energy mode"
                    " due to insufficient permissions."
                    "\nSee https://github.com/IanHarvey/bluepy/issues/313#issuecomment-428324639"
                    ", https://github.com/fphammerle/switchbot-mqtt/pull/31#issuecomment-846383603"
                    ", and https://github.com/IanHarvey/bluepy/blob/v/1.3.0/bluepy"
                    "/bluepy-helper.c#L1260."
                    "\nInsecure workaround:"
                    "\n1. sudo apt-get install --no-install-recommends libcap2-bin"
                    f"\n2. sudo setcap cap_net_admin+ep {shlex.quote(bluepy.btle.helperExe)}"
                    "\n3. restart switchbot-mqtt"
                    "\nIn docker-based setups, you could use"
                    " `sudo docker run --cap-drop ALL --cap-add NET_ADMIN --user 0 …`"
                    " (seriously insecure)."
                ) from exc
            raise

    def _report_battery_level(
        self, mqtt_client: paho.mqtt.client.Client, mqtt_topic_prefix: str
    ) -> None:
        # > battery: Percentage of battery that is left.
        # https://www.home-assistant.io/integrations/sensor/#device-class
        self._mqtt_publish(
            topic_prefix=mqtt_topic_prefix,
            topic_levels=self._MQTT_BATTERY_PERCENTAGE_TOPIC_LEVELS,
            payload=str(self._get_device().get_battery_percent()).encode(),
            mqtt_client=mqtt_client,
        )

    def _update_and_report_device_info(
        self, mqtt_client: paho.mqtt.client.Client, mqtt_topic_prefix: str
    ) -> None:
        self._update_device_info()
        self._report_battery_level(
            mqtt_client=mqtt_client, mqtt_topic_prefix=mqtt_topic_prefix
        )

    @classmethod
    def _init_from_topic(
        cls,
        topic: str,
        expected_topic_levels: typing.Collection[_MQTTTopicLevel],
        settings: _MQTTCallbackUserdata,
    ) -> typing.Optional[_MQTTControlledActor]:
        try:
            mac_address = _parse_mqtt_topic(
                topic=topic,
                expected_prefix=settings.mqtt_topic_prefix,
                expected_levels=expected_topic_levels,
            )[_MQTTTopicPlaceholder.MAC_ADDRESS]
        except ValueError as exc:
            _LOGGER.warning(str(exc), exc_info=False)
            return None
        if not _mac_address_valid(mac_address):
            _LOGGER.warning("invalid mac address %s", mac_address)
            return None
        return cls(
            mac_address=mac_address,
            retry_count=settings.retry_count,
            password=settings.device_passwords.get(mac_address, None),
        )

    @classmethod
    def _mqtt_update_device_info_callback(
        cls,
        mqtt_client: paho.mqtt.client.Client,
        userdata: _MQTTCallbackUserdata,
        message: paho.mqtt.client.MQTTMessage,
    ) -> None:
        # pylint: disable=unused-argument; callback
        # https://github.com/eclipse/paho.mqtt.python/blob/v1.5.0/src/paho/mqtt/client.py#L469
        _LOGGER.debug("received topic=%s payload=%r", message.topic, message.payload)
        if message.retain:
            _LOGGER.info("ignoring retained message")
            return
        actor = cls._init_from_topic(
            topic=message.topic,
            expected_topic_levels=cls._MQTT_UPDATE_DEVICE_INFO_TOPIC_LEVELS,
            settings=userdata,
        )
        if actor:
            # pylint: disable=protected-access; own instance
            actor._update_and_report_device_info(
                mqtt_client=mqtt_client, mqtt_topic_prefix=userdata.mqtt_topic_prefix
            )

    @abc.abstractmethod
    def execute_command(
        self,
        *,
        mqtt_message_payload: bytes,
        mqtt_client: paho.mqtt.client.Client,
        update_device_info: bool,
        mqtt_topic_prefix: str,
    ) -> None:
        raise NotImplementedError()

    @classmethod
    def _mqtt_command_callback(
        cls,
        mqtt_client: paho.mqtt.client.Client,
        userdata: _MQTTCallbackUserdata,
        message: paho.mqtt.client.MQTTMessage,
    ) -> None:
        # pylint: disable=unused-argument; callback
        # https://github.com/eclipse/paho.mqtt.python/blob/v1.5.0/src/paho/mqtt/client.py#L469
        _LOGGER.debug("received topic=%s payload=%r", message.topic, message.payload)
        if message.retain:
            _LOGGER.info("ignoring retained message")
            return
        actor = cls._init_from_topic(
            topic=message.topic,
            expected_topic_levels=cls.MQTT_COMMAND_TOPIC_LEVELS,
            settings=userdata,
        )
        if actor:
            actor.execute_command(
                mqtt_message_payload=message.payload,
                mqtt_client=mqtt_client,
                update_device_info=userdata.fetch_device_info,
                mqtt_topic_prefix=userdata.mqtt_topic_prefix,
            )

    @classmethod
    def _get_mqtt_message_callbacks(
        cls,
        *,
        enable_device_info_update_topic: bool,
    ) -> typing.Dict[typing.Tuple[_MQTTTopicLevel, ...], typing.Callable]:
        # returning dict because `paho.mqtt.client.Client.message_callback_add` overwrites
        # callbacks with same topic pattern
        # https://github.com/eclipse/paho.mqtt.python/blob/v1.6.1/src/paho/mqtt/client.py#L2304
        # https://github.com/eclipse/paho.mqtt.python/blob/v1.6.1/src/paho/mqtt/matcher.py#L19
        callbacks = {cls.MQTT_COMMAND_TOPIC_LEVELS: cls._mqtt_command_callback}
        if enable_device_info_update_topic:
            callbacks[
                cls._MQTT_UPDATE_DEVICE_INFO_TOPIC_LEVELS
            ] = cls._mqtt_update_device_info_callback
        return callbacks

    @classmethod
    def mqtt_subscribe(
        cls, *, mqtt_client: paho.mqtt.client.Client, settings: _MQTTCallbackUserdata
    ) -> None:
        for topic_levels, callback in cls._get_mqtt_message_callbacks(
            enable_device_info_update_topic=settings.fetch_device_info
        ).items():
            topic = _join_mqtt_topic_levels(
                topic_prefix=settings.mqtt_topic_prefix,
                topic_levels=topic_levels,
                mac_address="+",
            )
            _LOGGER.info("subscribing to MQTT topic %r", topic)
            mqtt_client.subscribe(topic)
            mqtt_client.message_callback_add(sub=topic, callback=callback)

    def _mqtt_publish(
        self,
        *,
        topic_prefix: str,
        topic_levels: typing.Iterable[_MQTTTopicLevel],
        payload: bytes,
        mqtt_client: paho.mqtt.client.Client,
    ) -> None:
        topic = _join_mqtt_topic_levels(
            topic_prefix=topic_prefix,
            topic_levels=topic_levels,
            mac_address=self._mac_address,
        )
        # https://pypi.org/project/paho-mqtt/#publishing
        _LOGGER.debug("publishing topic=%s payload=%r", topic, payload)
        message_info: paho.mqtt.client.MQTTMessageInfo = mqtt_client.publish(
            topic=topic, payload=payload, retain=True
        )
        # wait before checking status?
        if message_info.rc != paho.mqtt.client.MQTT_ERR_SUCCESS:
            _LOGGER.error(
                "Failed to publish MQTT message on topic %s (rc=%d)",
                topic,
                message_info.rc,
            )

    def report_state(
        self,
        state: bytes,
        mqtt_client: paho.mqtt.client.Client,
        mqtt_topic_prefix: str,
    ) -> None:
        self._mqtt_publish(
            topic_prefix=mqtt_topic_prefix,
            topic_levels=self.MQTT_STATE_TOPIC_LEVELS,
            payload=state,
            mqtt_client=mqtt_client,
        )
