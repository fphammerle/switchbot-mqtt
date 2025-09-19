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

# pylint: disable=protected-access
# pylint: disable=too-many-arguments; these are tests, no API
# pylint: disable=duplicate-code; similarities with tests for curtain motor

import logging
import unittest.mock

import _pytest.logging  # pylint: disable=import-private-name; typing
import pytest

# pylint: disable=import-private-name; internal
from switchbot_mqtt._actors import _ButtonAutomator

# pylint: disable=too-many-positional-arguments; tests


@pytest.mark.parametrize("prefix", ["homeassistant/", "prefix-", ""])
@pytest.mark.parametrize("mac_address", ["{MAC_ADDRESS}", "aa:bb:cc:dd:ee:ff"])
def test_get_mqtt_battery_percentage_topic(prefix: str, mac_address: str) -> None:
    assert (
        _ButtonAutomator.get_mqtt_battery_percentage_topic(
            prefix=prefix, mac_address=mac_address
        )
        == f"{prefix}switch/switchbot/{mac_address}/battery-percentage"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("topic_prefix", ["homeassistant/", "prefix-", ""])
@pytest.mark.parametrize(("battery_percent", "battery_percent_encoded"), [(42, b"42")])
async def test__update_and_report_device_info(
    topic_prefix: str, battery_percent: int, battery_percent_encoded: bytes
) -> None:
    device = unittest.mock.Mock()
    device.address = "dummy"
    with unittest.mock.patch("switchbot.Switchbot.__init__", return_value=None):
        actor = _ButtonAutomator(device=device, retry_count=21, password=None)
    actor._get_device().get_basic_info = unittest.mock.AsyncMock(
        return_value={"battery": battery_percent}
    )
    mqtt_client_mock = unittest.mock.AsyncMock()
    await actor._update_and_report_device_info(
        mqtt_client=mqtt_client_mock, mqtt_topic_prefix=topic_prefix
    )
    mqtt_client_mock.publish.assert_awaited_once_with(
        topic=f"{topic_prefix}switch/switchbot/dummy/battery-percentage",
        payload=battery_percent_encoded,
        retain=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("topic_prefix", ["homeassistant/"])
@pytest.mark.parametrize("mac_address", ["aa:bb:cc:dd:ee:ff", "aa:bb:cc:11:22:33"])
@pytest.mark.parametrize("password", (None, "secret"))
@pytest.mark.parametrize("retry_count", (3, 21))
@pytest.mark.parametrize(
    ("message_payload", "action_name"),
    [
        (b"on", "switchbot.Switchbot.turn_on"),
        (b"ON", "switchbot.Switchbot.turn_on"),
        (b"On", "switchbot.Switchbot.turn_on"),
        (b"off", "switchbot.Switchbot.turn_off"),
        (b"OFF", "switchbot.Switchbot.turn_off"),
        (b"Off", "switchbot.Switchbot.turn_off"),
    ],
)
@pytest.mark.parametrize("update_device_info", [True, False])
@pytest.mark.parametrize("command_successful", [True, False])
async def test_execute_command(
    caplog: _pytest.logging.LogCaptureFixture,
    topic_prefix: str,
    mac_address: str,
    password: str | None,
    retry_count: int,
    message_payload: bytes,
    action_name: str,
    update_device_info: bool,
    command_successful: bool,
) -> None:
    # pylint: disable=too-many-locals
    device = unittest.mock.Mock()
    device.address = mac_address
    with unittest.mock.patch(
        "switchbot.Switchbot.__init__", return_value=None
    ) as device_init_mock, caplog.at_level(logging.INFO):
        actor = _ButtonAutomator(
            device=device, retry_count=retry_count, password=password
        )
        mqtt_client = unittest.mock.Mock()
        with unittest.mock.patch.object(
            actor, "report_state"
        ) as report_mock, unittest.mock.patch(
            action_name, return_value=command_successful
        ) as action_mock, unittest.mock.patch.object(
            actor, "_update_and_report_device_info"
        ) as update_device_info_mock:
            await actor.execute_command(
                mqtt_client=mqtt_client,
                mqtt_message_payload=message_payload,
                update_device_info=update_device_info,
                mqtt_topic_prefix=topic_prefix,
            )
    device_init_mock.assert_called_once_with(
        device=device, password=password, retry_count=retry_count
    )
    action_mock.assert_awaited_once_with()
    if command_successful:
        assert caplog.record_tuples == [
            (
                "switchbot_mqtt._actors",
                logging.INFO,
                f"switchbot {mac_address} turned {message_payload.decode().lower()}",
            )
        ]
        report_mock.assert_awaited_once_with(
            mqtt_client=mqtt_client,
            mqtt_topic_prefix=topic_prefix,
            state=message_payload.upper(),
        )
        assert update_device_info_mock.await_count == (1 if update_device_info else 0)
    else:
        assert caplog.record_tuples == [
            (
                "switchbot_mqtt._actors",
                logging.ERROR,
                f"failed to turn {message_payload.decode().lower()} switchbot {mac_address}",
            )
        ]
        report_mock.assert_not_called()
        update_device_info_mock.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("mac_address", ["aa:bb:cc:dd:ee:ff"])
@pytest.mark.parametrize("message_payload", [b"EIN", b""])
async def test_execute_command_invalid_payload(
    caplog: _pytest.logging.LogCaptureFixture, mac_address: str, message_payload: bytes
) -> None:
    device = unittest.mock.Mock()
    device.address = mac_address
    with unittest.mock.patch("switchbot.Switchbot") as device_mock, caplog.at_level(
        logging.INFO
    ):
        actor = _ButtonAutomator(device=device, retry_count=21, password=None)
        with unittest.mock.patch.object(actor, "report_state") as report_mock:
            await actor.execute_command(
                mqtt_client=unittest.mock.Mock(),
                mqtt_message_payload=message_payload,
                update_device_info=True,
                mqtt_topic_prefix="dummy",
            )
    device_mock.assert_called_once_with(device=device, retry_count=21, password=None)
    assert not device_mock().mock_calls  # no methods called
    report_mock.assert_not_called()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors",
            logging.WARNING,
            f"unexpected payload {message_payload!r} (expected 'ON' or 'OFF')",
        )
    ]
