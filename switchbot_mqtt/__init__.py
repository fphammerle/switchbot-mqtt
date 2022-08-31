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
import typing

import paho.mqtt.client

from switchbot_mqtt._actors import _ButtonAutomator, _CurtainMotor
from switchbot_mqtt._actors.base import _MQTTCallbackUserdata

_LOGGER = logging.getLogger(__name__)

_MQTT_AVAILABILITY_TOPIC = "switchbot-mqtt/status"
# "online" and "offline" to match home assistant's default settings
# https://www.home-assistant.io/integrations/switch.mqtt/#payload_available
_MQTT_BIRTH_PAYLOAD = "online"
_MQTT_LAST_WILL_PAYLOAD = "offline"


def _mqtt_on_connect(
    mqtt_client: paho.mqtt.client.Client,
    userdata: _MQTTCallbackUserdata,
    flags: typing.Dict[str, int],
    return_code: int,
) -> None:
    # pylint: disable=unused-argument; callback
    # https://github.com/eclipse/paho.mqtt.python/blob/v1.5.0/src/paho/mqtt/client.py#L441
    assert return_code == 0, return_code  # connection accepted
    mqtt_broker_host, mqtt_broker_port, *_ = mqtt_client.socket().getpeername()
    # https://www.rfc-editor.org/rfc/rfc5952#section-6
    _LOGGER.debug(
        "connected to MQTT broker %s:%d",
        f"[{mqtt_broker_host}]"
        if mqtt_client.socket().family == socket.AF_INET6
        else mqtt_broker_host,
        mqtt_broker_port,
    )
    mqtt_client.publish(
        topic=userdata.mqtt_topic_prefix + _MQTT_AVAILABILITY_TOPIC,
        payload=_MQTT_BIRTH_PAYLOAD,
        retain=True,
    )
    _ButtonAutomator.mqtt_subscribe(mqtt_client=mqtt_client, settings=userdata)
    _CurtainMotor.mqtt_subscribe(mqtt_client=mqtt_client, settings=userdata)


def _run(
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
    # https://pypi.org/project/paho-mqtt/
    mqtt_client = paho.mqtt.client.Client(
        userdata=_MQTTCallbackUserdata(
            retry_count=retry_count,
            device_passwords=device_passwords,
            fetch_device_info=fetch_device_info,
            mqtt_topic_prefix=mqtt_topic_prefix,
        )
    )
    mqtt_client.on_connect = _mqtt_on_connect
    _LOGGER.info(
        "connecting to MQTT broker %s:%d (TLS %s)",
        mqtt_host,
        mqtt_port,
        "disabled" if mqtt_disable_tls else "enabled",
    )
    if not mqtt_disable_tls:
        mqtt_client.tls_set(ca_certs=None)  # enable tls trusting default system certs
    if mqtt_username:
        mqtt_client.username_pw_set(username=mqtt_username, password=mqtt_password)
    elif mqtt_password:
        raise ValueError("Missing MQTT username")
    mqtt_client.will_set(
        topic=mqtt_topic_prefix + _MQTT_AVAILABILITY_TOPIC,
        payload=_MQTT_LAST_WILL_PAYLOAD,
        retain=True,
    )
    mqtt_client.connect(host=mqtt_host, port=mqtt_port)
    # https://github.com/eclipse/paho.mqtt.python/blob/master/src/paho/mqtt/client.py#L1740
    mqtt_client.loop_forever()
