# switchbot-mqtt - MQTT client controlling SwitchBot button & curtain automators,
# compatible with home-assistant.io's MQTT Switch & Cover platform
#
# Copyright (C) 2022 Fabian Peter Hammerle <fabian@hammerle.me>
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
import unittest.mock

import _pytest.logging
import pytest
from paho.mqtt.client import MQTTMessage

from switchbot_mqtt._actors import _CurtainMotor
from switchbot_mqtt._actors.base import _MQTTCallbackUserdata

# pylint: disable=protected-access


@pytest.mark.parametrize(
    ("topic", "payload", "expected_mac_address", "expected_position_percent"),
    [
        (
            b"home/cover/switchbot-curtain/aa:bb:cc:dd:ee:ff/position/set-percent",
            b"42",
            "aa:bb:cc:dd:ee:ff",
            42,
        ),
        (
            b"home/cover/switchbot-curtain/11:22:33:44:55:66/position/set-percent",
            b"0",
            "11:22:33:44:55:66",
            0,
        ),
        (
            b"home/cover/switchbot-curtain/11:22:33:44:55:66/position/set-percent",
            b"100",
            "11:22:33:44:55:66",
            100,
        ),
    ],
)
@pytest.mark.parametrize("retry_count", (3, 42))
def test__mqtt_set_position_callback(
    caplog: _pytest.logging.LogCaptureFixture,
    topic: bytes,
    payload: bytes,
    expected_mac_address: str,
    retry_count: int,
    expected_position_percent: int,
) -> None:
    callback_userdata = _MQTTCallbackUserdata(
        retry_count=retry_count,
        device_passwords={},
        fetch_device_info=False,
        mqtt_topic_prefix="home/",
    )
    message = MQTTMessage(topic=topic)
    message.payload = payload
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain"
    ) as device_init_mock, caplog.at_level(logging.DEBUG):
        _CurtainMotor._mqtt_set_position_callback(
            mqtt_client="client dummy", userdata=callback_userdata, message=message
        )
    device_init_mock.assert_called_once_with(
        mac=expected_mac_address,
        password=None,
        retry_count=retry_count,
        reverse_mode=True,
    )
    device_init_mock().set_position.assert_called_once_with(expected_position_percent)
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors",
            logging.DEBUG,
            f"received topic=home/cover/switchbot-curtain/{expected_mac_address}"
            f"/position/set-percent payload=b'{expected_position_percent}'",
        ),
        (
            "switchbot_mqtt._actors",
            logging.INFO,
            f"set position of switchbot curtain {expected_mac_address}"
            f" to {expected_position_percent}%",
        ),
    ]


def test__mqtt_set_position_callback_ignore_retained(
    caplog: _pytest.logging.LogCaptureFixture,
) -> None:
    callback_userdata = _MQTTCallbackUserdata(
        retry_count=3,
        device_passwords={},
        fetch_device_info=False,
        mqtt_topic_prefix="whatever",
    )
    message = MQTTMessage(
        topic=b"homeassistant/cover/switchbot-curtain/aa:bb:cc:dd:ee:ff/position/set-percent"
    )
    message.payload = b"42"
    message.retain = True
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain"
    ) as device_init_mock, caplog.at_level(logging.INFO):
        _CurtainMotor._mqtt_set_position_callback(
            mqtt_client="client dummy", userdata=callback_userdata, message=message
        )
    device_init_mock.assert_not_called()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors",
            logging.INFO,
            "ignoring retained message on topic"
            " homeassistant/cover/switchbot-curtain/aa:bb:cc:dd:ee:ff/position/set-percent",
        ),
    ]


def test__mqtt_set_position_callback_unexpected_topic(
    caplog: _pytest.logging.LogCaptureFixture,
) -> None:
    callback_userdata = _MQTTCallbackUserdata(
        retry_count=3,
        device_passwords={},
        fetch_device_info=False,
        mqtt_topic_prefix="",
    )
    message = MQTTMessage(topic=b"switchbot-curtain/aa:bb:cc:dd:ee:ff/position/set")
    message.payload = b"42"
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain"
    ) as device_init_mock, caplog.at_level(logging.INFO):
        _CurtainMotor._mqtt_set_position_callback(
            mqtt_client="client dummy", userdata=callback_userdata, message=message
        )
    device_init_mock.assert_not_called()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors.base",
            logging.WARN,
            "unexpected topic switchbot-curtain/aa:bb:cc:dd:ee:ff/position/set",
        ),
    ]


def test__mqtt_set_position_callback_invalid_mac_address(
    caplog: _pytest.logging.LogCaptureFixture,
) -> None:
    callback_userdata = _MQTTCallbackUserdata(
        retry_count=3,
        device_passwords={},
        fetch_device_info=False,
        mqtt_topic_prefix="tnatsissaemoh/",
    )
    message = MQTTMessage(
        topic=b"tnatsissaemoh/cover/switchbot-curtain/aa:bb:cc:dd:ee/position/set-percent"
    )
    message.payload = b"42"
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain"
    ) as device_init_mock, caplog.at_level(logging.INFO):
        _CurtainMotor._mqtt_set_position_callback(
            mqtt_client="client dummy", userdata=callback_userdata, message=message
        )
    device_init_mock.assert_not_called()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors.base",
            logging.WARN,
            "invalid mac address aa:bb:cc:dd:ee",
        ),
    ]


@pytest.mark.parametrize("payload", [b"-1", b"123"])
def test__mqtt_set_position_callback_invalid_position(
    caplog: _pytest.logging.LogCaptureFixture,
    payload: bytes,
) -> None:
    callback_userdata = _MQTTCallbackUserdata(
        retry_count=3,
        device_passwords={},
        fetch_device_info=False,
        mqtt_topic_prefix="homeassistant/",
    )
    message = MQTTMessage(
        topic=b"homeassistant/cover/switchbot-curtain/aa:bb:cc:dd:ee:ff/position/set-percent"
    )
    message.payload = payload
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain"
    ) as device_init_mock, caplog.at_level(logging.INFO):
        _CurtainMotor._mqtt_set_position_callback(
            mqtt_client="client dummy", userdata=callback_userdata, message=message
        )
    device_init_mock.assert_called_once()
    device_init_mock().set_position.assert_not_called()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors",
            logging.WARN,
            f"invalid position {payload.decode()}%, ignoring message",
        ),
    ]


def test__mqtt_set_position_callback_command_failed(
    caplog: _pytest.logging.LogCaptureFixture,
) -> None:
    callback_userdata = _MQTTCallbackUserdata(
        retry_count=3,
        device_passwords={},
        fetch_device_info=False,
        mqtt_topic_prefix="",
    )
    message = MQTTMessage(
        topic=b"cover/switchbot-curtain/aa:bb:cc:dd:ee:ff/position/set-percent"
    )
    message.payload = b"21"
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain"
    ) as device_init_mock, caplog.at_level(logging.INFO):
        device_init_mock().set_position.return_value = False
        device_init_mock.reset_mock()
        _CurtainMotor._mqtt_set_position_callback(
            mqtt_client="client dummy", userdata=callback_userdata, message=message
        )
    device_init_mock.assert_called_once()
    device_init_mock().set_position.assert_called_with(21)
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors",
            logging.ERROR,
            "failed to set position of switchbot curtain aa:bb:cc:dd:ee:ff",
        ),
    ]
