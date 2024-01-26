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
import socket
import ssl
import typing

import aiomqtt

from switchbot_mqtt._actors import _ButtonAutomator, _CurtainMotor

_LOGGER = logging.getLogger(__name__)

_MQTT_AVAILABILITY_TOPIC = "switchbot-mqtt/status"
# "online" and "offline" to match home assistant's default settings
# https://www.home-assistant.io/integrations/switch.mqtt/#payload_available
_MQTT_BIRTH_PAYLOAD = "online"
_MQTT_LAST_WILL_PAYLOAD = "offline"


async def _listen(
    *,
    mqtt_client: aiomqtt.Client,
    topic_callbacks: typing.Iterable[typing.Tuple[str, typing.Callable]],
    mqtt_topic_prefix: str,
    retry_count: int,
    device_passwords: typing.Dict[str, str],
    fetch_device_info: bool,
) -> None:
    async with mqtt_client.messages() as messages:
        await mqtt_client.publish(
            topic=mqtt_topic_prefix + _MQTT_AVAILABILITY_TOPIC,
            payload=_MQTT_BIRTH_PAYLOAD,
            retain=True,
        )
        async for message in messages:
            for topic, callback in topic_callbacks:
                if message.topic.matches(topic):
                    await callback(
                        mqtt_client=mqtt_client,
                        message=message,
                        mqtt_topic_prefix=mqtt_topic_prefix,
                        retry_count=retry_count,
                        device_passwords=device_passwords,
                        fetch_device_info=fetch_device_info,
                    )


def _log_mqtt_connected(mqtt_client: aiomqtt.Client) -> None:
    if _LOGGER.getEffectiveLevel() <= logging.DEBUG:
        mqtt_socket = (
            # aiomqtt neither exposes instance of paho.mqtt.client.Client nor socket publicly.
            # level condition to avoid accessing protected `mqtt_client._client` in production.
            # pylint: disable=protected-access
            mqtt_client._client.socket()
        )
        (mqtt_broker_host, mqtt_broker_port, *_) = mqtt_socket.getpeername()
        # https://github.com/sbtinstruments/aiomqtt/blob/v1.2.1/aiomqtt/client.py#L1089
        _LOGGER.debug(
            "connected to MQTT broker %s:%d",
            (
                f"[{mqtt_broker_host}]"
                if mqtt_socket.family == socket.AF_INET6
                else mqtt_broker_host
            ),
            mqtt_broker_port,
        )


async def _run(  # pylint: disable=too-many-arguments
    *,
    mqtt_host: str,
    mqtt_port: int,
    mqtt_disable_tls: bool,
    mqtt_username: typing.Optional[str],
    mqtt_password: typing.Optional[str],
    mqtt_topic_prefix: str,
    retry_count: int,
    device_passwords: typing.Dict[str, str],
    fetch_device_info: bool,
) -> None:
    _LOGGER.info(
        "connecting to MQTT broker %s:%d (TLS %s)",
        mqtt_host,
        mqtt_port,
        "disabled" if mqtt_disable_tls else "enabled",
    )
    if mqtt_password is not None and mqtt_username is None:
        raise ValueError("Missing MQTT username")
    async with aiomqtt.Client(  # raises aiomqtt.MqttError
        hostname=mqtt_host,
        port=mqtt_port,
        # > The settings [...] usually represent a higher security level than
        # > when calling the SSLContext constructor directly.
        # https://web.archive.org/web/20230714183106/https://docs.python.org/3/library/ssl.html
        tls_context=None if mqtt_disable_tls else ssl.create_default_context(),
        username=None if mqtt_username is None else mqtt_username,
        password=None if mqtt_password is None else mqtt_password,
        will=aiomqtt.Will(
            topic=mqtt_topic_prefix + _MQTT_AVAILABILITY_TOPIC,
            payload=_MQTT_LAST_WILL_PAYLOAD,
            retain=True,
        ),
    ) as mqtt_client:
        _log_mqtt_connected(mqtt_client=mqtt_client)
        topic_callbacks: typing.List[typing.Tuple[str, typing.Callable]] = []
        for actor_class in (_ButtonAutomator, _CurtainMotor):
            async for topic, callback in actor_class.mqtt_subscribe(
                mqtt_client=mqtt_client,
                mqtt_topic_prefix=mqtt_topic_prefix,
                fetch_device_info=fetch_device_info,
            ):
                topic_callbacks.append((topic, callback))
        await _listen(
            mqtt_client=mqtt_client,
            topic_callbacks=topic_callbacks,
            mqtt_topic_prefix=mqtt_topic_prefix,
            retry_count=retry_count,
            device_passwords=device_passwords,
            fetch_device_info=fetch_device_info,
        )
