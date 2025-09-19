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

import aiomqtt
import bleak
import _pytest.logging  # pylint: disable=import-private-name; typing
import pytest

# pylint: disable=import-private-name; internal
from switchbot_mqtt._actors import _CurtainMotor

# pylint: disable=protected-access,too-many-positional-arguments


def _create_mqtt_message(
    *, topic: str, payload: bytes, retain: bool = False
) -> aiomqtt.Message:
    return aiomqtt.Message(
        topic=topic, payload=payload, qos=0, retain=retain, mid=0, properties=None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("topic", "payload", "expected_mac_address", "expected_position_percent"),
    [
        (
            "home/cover/switchbot-curtain/aa:bb:cc:dd:ee:ff/position/set-percent",
            b"42",
            "aa:bb:cc:dd:ee:ff",
            42,
        ),
        (
            "home/cover/switchbot-curtain/11:22:33:44:55:66/position/set-percent",
            b"0",
            "11:22:33:44:55:66",
            0,
        ),
        (
            "home/cover/switchbot-curtain/11:22:33:44:55:66/position/set-percent",
            b"100",
            "11:22:33:44:55:66",
            100,
        ),
    ],
)
@pytest.mark.parametrize("retry_count", (3, 42))
async def test__mqtt_set_position_callback(
    caplog: _pytest.logging.LogCaptureFixture,
    topic: str,
    payload: bytes,
    expected_mac_address: str,
    retry_count: int,
    expected_position_percent: int,
) -> None:
    message = _create_mqtt_message(topic=topic, payload=payload)
    device = unittest.mock.Mock()
    device.address = expected_mac_address
    with unittest.mock.patch.object(
        bleak.BleakScanner, "find_device_by_address", return_value=device
    ), unittest.mock.patch(
        "switchbot.SwitchbotCurtain.__init__", return_value=None
    ) as device_init_mock, unittest.mock.patch(
        "switchbot.SwitchbotCurtain.set_position"
    ) as set_position_mock, caplog.at_level(
        logging.DEBUG
    ):
        await _CurtainMotor._mqtt_set_position_callback(
            mqtt_client=unittest.mock.Mock(),
            message=message,
            retry_count=retry_count,
            device_passwords={},
            fetch_device_info=False,
            mqtt_topic_prefix="home/",
        )
    device_init_mock.assert_called_once_with(
        device=device, password=None, retry_count=retry_count, reverse_mode=True
    )
    set_position_mock.assert_called_once_with(expected_position_percent)
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


@pytest.mark.asyncio
async def test__mqtt_set_position_callback_ignore_retained(
    caplog: _pytest.logging.LogCaptureFixture,
) -> None:
    message = _create_mqtt_message(
        topic="homeassistant/cover/switchbot-curtain/aa:bb:cc:dd:ee:ff/position/set-percent",
        payload=b"42",
        retain=True,
    )
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain"
    ) as device_init_mock, caplog.at_level(logging.INFO):
        await _CurtainMotor._mqtt_set_position_callback(
            mqtt_client=unittest.mock.Mock(),
            message=message,
            retry_count=3,
            device_passwords={},
            fetch_device_info=False,
            mqtt_topic_prefix="whatever",
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


@pytest.mark.asyncio
async def test__mqtt_set_position_callback_unexpected_topic(
    caplog: _pytest.logging.LogCaptureFixture,
) -> None:
    message = _create_mqtt_message(
        topic="switchbot-curtain/aa:bb:cc:dd:ee:ff/position/set", payload=b"42"
    )
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain"
    ) as device_init_mock, caplog.at_level(logging.INFO):
        await _CurtainMotor._mqtt_set_position_callback(
            mqtt_client=unittest.mock.Mock(),
            message=message,
            retry_count=3,
            device_passwords={},
            fetch_device_info=False,
            mqtt_topic_prefix="",
        )
    device_init_mock.assert_not_called()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors.base",
            logging.WARN,
            "unexpected topic switchbot-curtain/aa:bb:cc:dd:ee:ff/position/set",
        ),
    ]


@pytest.mark.asyncio
async def test__mqtt_set_position_callback_invalid_mac_address(
    caplog: _pytest.logging.LogCaptureFixture,
) -> None:
    message = _create_mqtt_message(
        topic="tnatsissaemoh/cover/switchbot-curtain/aa:bb:cc:dd:ee/position/set-percent",
        payload=b"42",
    )
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain"
    ) as device_init_mock, caplog.at_level(logging.INFO):
        await _CurtainMotor._mqtt_set_position_callback(
            mqtt_client=unittest.mock.Mock(),
            message=message,
            retry_count=3,
            device_passwords={},
            fetch_device_info=False,
            mqtt_topic_prefix="tnatsissaemoh/",
        )
    device_init_mock.assert_not_called()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors.base",
            logging.WARN,
            "invalid mac address aa:bb:cc:dd:ee",
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [b"-1", b"123"])
async def test__mqtt_set_position_callback_invalid_position(
    caplog: _pytest.logging.LogCaptureFixture,
    payload: bytes,
) -> None:
    message = _create_mqtt_message(
        topic="homeassistant/cover/switchbot-curtain/aa:bb:cc:dd:ee:ff/position/set-percent",
        payload=payload,
    )
    with unittest.mock.patch.object(
        bleak.BleakScanner, "find_device_by_address"
    ), unittest.mock.patch(
        "switchbot.SwitchbotCurtain"
    ) as device_init_mock, caplog.at_level(
        logging.INFO
    ):
        await _CurtainMotor._mqtt_set_position_callback(
            mqtt_client=unittest.mock.Mock(),
            message=message,
            retry_count=3,
            device_passwords={},
            fetch_device_info=False,
            mqtt_topic_prefix="homeassistant/",
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


@pytest.mark.asyncio
async def test__mqtt_set_position_callback_command_failed(
    caplog: _pytest.logging.LogCaptureFixture,
) -> None:
    message = _create_mqtt_message(
        topic="cover/switchbot-curtain/aa:bb:cc:dd:ee:ff/position/set-percent",
        payload=b"21",
    )
    device = unittest.mock.Mock()
    device.address = "aa:bb:cc:dd:ee:ff"
    with unittest.mock.patch.object(
        bleak.BleakScanner, "find_device_by_address", return_value=device
    ), unittest.mock.patch(
        "switchbot.SwitchbotCurtain.__init__", return_value=None
    ) as device_init_mock, unittest.mock.patch(
        "switchbot.SwitchbotCurtain.set_position", return_value=False
    ) as set_position_mock, caplog.at_level(
        logging.INFO
    ):
        await _CurtainMotor._mqtt_set_position_callback(
            mqtt_client=unittest.mock.Mock(),
            message=message,
            retry_count=3,
            device_passwords={},
            fetch_device_info=False,
            mqtt_topic_prefix="",
        )
    device_init_mock.assert_called_once()
    set_position_mock.assert_awaited_with(21)
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors",
            logging.ERROR,
            "failed to set position of switchbot curtain aa:bb:cc:dd:ee:ff",
        ),
    ]
