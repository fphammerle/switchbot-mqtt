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
import unittest.mock

import bluepy.btle
import pytest

import switchbot_mqtt

# pylint: disable=protected-access
# pylint: disable=too-many-arguments; these are tests, no API


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
@pytest.mark.parametrize("command_successful", [True, False])
def test_execute_command(
    caplog,
    mac_address,
    password,
    retry_count,
    message_payload,
    action_name,
    command_successful,
):
    with unittest.mock.patch(
        "switchbot.Switchbot.__init__", return_value=None
    ) as device_init_mock, caplog.at_level(logging.INFO):
        actor = switchbot_mqtt._ButtonAutomator(
            mac_address=mac_address, retry_count=retry_count, password=password
        )
        with unittest.mock.patch.object(
            actor, "report_state"
        ) as report_mock, unittest.mock.patch(
            action_name, return_value=command_successful
        ) as action_mock:
            actor.execute_command(
                mqtt_client="dummy",
                mqtt_message_payload=message_payload,
                update_device_info=True,
            )
    device_init_mock.assert_called_once_with(
        mac=mac_address, password=password, retry_count=retry_count
    )
    action_mock.assert_called_once_with()
    if command_successful:
        assert caplog.record_tuples == [
            (
                "switchbot_mqtt",
                logging.INFO,
                "switchbot {} turned {}".format(
                    mac_address, message_payload.decode().lower()
                ),
            )
        ]
        report_mock.assert_called_once_with(
            mqtt_client="dummy", state=message_payload.upper()
        )
    else:
        assert caplog.record_tuples == [
            (
                "switchbot_mqtt",
                logging.ERROR,
                "failed to turn {} switchbot {}".format(
                    message_payload.decode().lower(), mac_address
                ),
            )
        ]
        report_mock.assert_not_called()


@pytest.mark.parametrize("mac_address", ["aa:bb:cc:dd:ee:ff"])
@pytest.mark.parametrize("message_payload", [b"EIN", b""])
def test_execute_command_invalid_payload(caplog, mac_address, message_payload):
    with unittest.mock.patch("switchbot.Switchbot") as device_mock, caplog.at_level(
        logging.INFO
    ):
        actor = switchbot_mqtt._ButtonAutomator(
            mac_address=mac_address, retry_count=21, password=None
        )
        with unittest.mock.patch.object(actor, "report_state") as report_mock:
            actor.execute_command(
                mqtt_client="dummy",
                mqtt_message_payload=message_payload,
                update_device_info=True,
            )
    device_mock.assert_called_once_with(mac=mac_address, retry_count=21, password=None)
    assert not device_mock().mock_calls  # no methods called
    report_mock.assert_not_called()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt",
            logging.WARNING,
            "unexpected payload {!r} (expected 'ON' or 'OFF')".format(message_payload),
        )
    ]


@pytest.mark.parametrize("mac_address", ["aa:bb:cc:dd:ee:ff"])
@pytest.mark.parametrize("message_payload", [b"ON", b"OFF"])
def test_execute_command_bluetooth_error(caplog, mac_address, message_payload):
    """
    paho.mqtt.python>=1.5.1 no longer implicitly suppresses exceptions in callbacks.
    verify pySwitchbot catches exceptions raised in bluetooth stack.
    https://github.com/Danielhiversen/pySwitchbot/blob/0.8.0/switchbot/__init__.py#L48
    https://github.com/Danielhiversen/pySwitchbot/blob/0.8.0/switchbot/__init__.py#L94
    """
    with unittest.mock.patch(
        "bluepy.btle.Peripheral",
        side_effect=bluepy.btle.BTLEDisconnectError(
            "Failed to connect to peripheral {}, addr type: random".format(mac_address)
        ),
    ), caplog.at_level(logging.ERROR):
        switchbot_mqtt._ButtonAutomator(
            mac_address=mac_address, retry_count=3, password=None
        ).execute_command(
            mqtt_client="dummy",
            mqtt_message_payload=message_payload,
            update_device_info=True,
        )
    assert caplog.record_tuples == [
        (
            "switchbot",
            logging.ERROR,
            "Switchbot communication failed. Stopping trying.",
        ),
        (
            "switchbot_mqtt",
            logging.ERROR,
            "failed to turn {} switchbot {}".format(
                message_payload.decode().lower(), mac_address
            ),
        ),
    ]
