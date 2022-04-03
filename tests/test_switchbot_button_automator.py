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
import unittest.mock

import _pytest.logging
import bluepy.btle
import pytest

from switchbot_mqtt._actors import _ButtonAutomator

# pylint: disable=protected-access
# pylint: disable=too-many-arguments; these are tests, no API


@pytest.mark.parametrize("prefix", ["homeassistant/", "prefix-", ""])
@pytest.mark.parametrize("mac_address", ["{MAC_ADDRESS}", "aa:bb:cc:dd:ee:ff"])
def test_get_mqtt_battery_percentage_topic(prefix: str, mac_address: str) -> None:
    assert (
        _ButtonAutomator.get_mqtt_battery_percentage_topic(
            prefix=prefix, mac_address=mac_address
        )
        == f"{prefix}switch/switchbot/{mac_address}/battery-percentage"
    )


@pytest.mark.parametrize("topic_prefix", ["homeassistant/", "prefix-", ""])
@pytest.mark.parametrize(("battery_percent", "battery_percent_encoded"), [(42, b"42")])
def test__update_and_report_device_info(
    topic_prefix: str, battery_percent: int, battery_percent_encoded: bytes
) -> None:
    with unittest.mock.patch("switchbot.SwitchbotCurtain.__init__", return_value=None):
        actor = _ButtonAutomator(mac_address="dummy", retry_count=21, password=None)
    actor._get_device()._switchbot_device_data = {"data": {"battery": battery_percent}}
    mqtt_client_mock = unittest.mock.MagicMock()
    with unittest.mock.patch("switchbot.Switchbot.update") as update_mock:
        actor._update_and_report_device_info(
            mqtt_client=mqtt_client_mock, mqtt_topic_prefix=topic_prefix
        )
    update_mock.assert_called_once_with()
    mqtt_client_mock.publish.assert_called_once_with(
        topic=f"{topic_prefix}switch/switchbot/dummy/battery-percentage",
        payload=battery_percent_encoded,
        retain=True,
    )


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
def test_execute_command(
    caplog: _pytest.logging.LogCaptureFixture,
    topic_prefix: str,
    mac_address: str,
    password: typing.Optional[str],
    retry_count: int,
    message_payload: bytes,
    action_name: str,
    update_device_info: bool,
    command_successful: bool,
) -> None:
    with unittest.mock.patch(
        "switchbot.Switchbot.__init__", return_value=None
    ) as device_init_mock, caplog.at_level(logging.INFO):
        actor = _ButtonAutomator(
            mac_address=mac_address, retry_count=retry_count, password=password
        )
        with unittest.mock.patch.object(
            actor, "report_state"
        ) as report_mock, unittest.mock.patch(
            action_name, return_value=command_successful
        ) as action_mock, unittest.mock.patch.object(
            actor, "_update_and_report_device_info"
        ) as update_device_info_mock:
            actor.execute_command(
                mqtt_client="dummy",
                mqtt_message_payload=message_payload,
                update_device_info=update_device_info,
                mqtt_topic_prefix=topic_prefix,
            )
    device_init_mock.assert_called_once_with(
        mac=mac_address, password=password, retry_count=retry_count
    )
    action_mock.assert_called_once_with()
    if command_successful:
        assert caplog.record_tuples == [
            (
                "switchbot_mqtt._actors",
                logging.INFO,
                f"switchbot {mac_address} turned {message_payload.decode().lower()}",
            )
        ]
        report_mock.assert_called_once_with(
            mqtt_client="dummy",
            mqtt_topic_prefix=topic_prefix,
            state=message_payload.upper(),
        )
        assert update_device_info_mock.call_count == (1 if update_device_info else 0)
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


@pytest.mark.parametrize("mac_address", ["aa:bb:cc:dd:ee:ff"])
@pytest.mark.parametrize("message_payload", [b"EIN", b""])
def test_execute_command_invalid_payload(
    caplog: _pytest.logging.LogCaptureFixture, mac_address: str, message_payload: bytes
) -> None:
    with unittest.mock.patch("switchbot.Switchbot") as device_mock, caplog.at_level(
        logging.INFO
    ):
        actor = _ButtonAutomator(mac_address=mac_address, retry_count=21, password=None)
        with unittest.mock.patch.object(actor, "report_state") as report_mock:
            actor.execute_command(
                mqtt_client="dummy",
                mqtt_message_payload=message_payload,
                update_device_info=True,
                mqtt_topic_prefix="dummy",
            )
    device_mock.assert_called_once_with(mac=mac_address, retry_count=21, password=None)
    assert not device_mock().mock_calls  # no methods called
    report_mock.assert_not_called()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors",
            logging.WARNING,
            f"unexpected payload {message_payload!r} (expected 'ON' or 'OFF')",
        )
    ]


@pytest.mark.parametrize("mac_address", ["aa:bb:cc:dd:ee:ff"])
@pytest.mark.parametrize("message_payload", [b"ON", b"OFF"])
def test_execute_command_bluetooth_error(
    caplog: _pytest.logging.LogCaptureFixture, mac_address: str, message_payload: bytes
) -> None:
    """
    paho.mqtt.python>=1.5.1 no longer implicitly suppresses exceptions in callbacks.
    verify pySwitchbot catches exceptions raised in bluetooth stack.
    https://github.com/Danielhiversen/pySwitchbot/blob/0.8.0/switchbot/__init__.py#L48
    https://github.com/Danielhiversen/pySwitchbot/blob/0.8.0/switchbot/__init__.py#L94
    """
    with unittest.mock.patch(
        "bluepy.btle.Peripheral",
        side_effect=bluepy.btle.BTLEDisconnectError(
            f"Failed to connect to peripheral {mac_address}, addr type: random"
        ),
    ), caplog.at_level(logging.ERROR):
        _ButtonAutomator(
            mac_address=mac_address, retry_count=0, password=None
        ).execute_command(
            mqtt_client="dummy",
            mqtt_message_payload=message_payload,
            update_device_info=True,
            mqtt_topic_prefix="dummy",
        )
    assert len(caplog.records) == 2
    assert caplog.records[0].name == "switchbot"
    assert caplog.records[0].levelno == logging.ERROR
    assert caplog.records[0].msg.startswith(
        # pySwitchbot<0.11 had '.' suffix
        "Switchbot communication failed. Stopping trying",
    )
    assert caplog.record_tuples[1] == (
        "switchbot_mqtt._actors",
        logging.ERROR,
        f"failed to turn {message_payload.decode().lower()} switchbot {mac_address}",
    )
