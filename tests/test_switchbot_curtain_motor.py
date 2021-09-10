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

# pylint: disable=protected-access,
# pylint: disable=too-many-arguments; these are tests, no API


@pytest.mark.parametrize(
    "mac_address",
    ("aa:bb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:gg"),
)
@pytest.mark.parametrize(
    ("position", "expected_payload"), [(0, b"0"), (100, b"100"), (42, b"42")]
)
def test__report_position(
    caplog, mac_address: str, position: int, expected_payload: bytes
):
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain.__init__", return_value=None
    ) as device_init_mock, caplog.at_level(logging.DEBUG):
        actor = switchbot_mqtt._CurtainMotor(
            mac_address=mac_address, retry_count=7, password=None
        )
    device_init_mock.assert_called_once_with(
        mac=mac_address,
        retry_count=7,
        password=None,
        # > The position of the curtain is saved in self._pos with 0 = open and 100 = closed.
        # > [...] The parameter 'reverse_mode' reverse these values, [...]
        # > The parameter is default set to True so that the definition of position
        # > is the same as in Home Assistant.
        # https://github.com/Danielhiversen/pySwitchbot/blob/0.10.0/switchbot/__init__.py#L150
        reverse_mode=True,
    )
    with unittest.mock.patch.object(
        actor, "_mqtt_publish"
    ) as publish_mock, unittest.mock.patch(
        "switchbot.SwitchbotCurtain.get_position", return_value=position
    ):
        actor._report_position(mqtt_client="dummy")
    publish_mock.assert_called_once_with(
        topic_levels=[
            "homeassistant",
            "cover",
            "switchbot-curtain",
            switchbot_mqtt._MQTTTopicPlaceholder.MAC_ADDRESS,
            "position",
        ],
        payload=expected_payload,
        mqtt_client="dummy",
    )
    assert not caplog.record_tuples


@pytest.mark.parametrize("position", ("", 'lambda: print("")'))
def test__report_position_invalid(caplog, position):
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain.__init__", return_value=None
    ), caplog.at_level(logging.DEBUG):
        actor = switchbot_mqtt._CurtainMotor(
            mac_address="aa:bb:cc:dd:ee:ff", retry_count=3, password=None
        )
    with unittest.mock.patch.object(
        actor, "_mqtt_publish"
    ) as publish_mock, unittest.mock.patch(
        "switchbot.SwitchbotCurtain.get_position", return_value=position
    ), pytest.raises(
        ValueError
    ):
        actor._report_position(mqtt_client="dummy")
    publish_mock.assert_not_called()


def test__update_position():
    with unittest.mock.patch("switchbot.SwitchbotCurtain.__init__", return_value=None):
        actor = switchbot_mqtt._CurtainMotor(
            mac_address="dummy", retry_count=21, password=None
        )
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain.update"
    ) as update_mock, unittest.mock.patch.object(
        actor, "_report_position"
    ) as report_position_mock:
        actor._update_position(mqtt_client="client")
    update_mock.assert_called_once_with()
    report_position_mock.assert_called_once_with(mqtt_client="client")


@pytest.mark.parametrize("mac_address", ["aa:bb:cc:dd:ee:ff", "aa:bb:cc:11:22:33"])
@pytest.mark.parametrize("password", ["pa$$word", None])
@pytest.mark.parametrize("retry_count", (2, 3))
@pytest.mark.parametrize(
    ("message_payload", "action_name"),
    [
        (b"open", "switchbot.SwitchbotCurtain.open"),
        (b"OPEN", "switchbot.SwitchbotCurtain.open"),
        (b"Open", "switchbot.SwitchbotCurtain.open"),
        (b"close", "switchbot.SwitchbotCurtain.close"),
        (b"CLOSE", "switchbot.SwitchbotCurtain.close"),
        (b"Close", "switchbot.SwitchbotCurtain.close"),
        (b"stop", "switchbot.SwitchbotCurtain.stop"),
        (b"STOP", "switchbot.SwitchbotCurtain.stop"),
        (b"Stop", "switchbot.SwitchbotCurtain.stop"),
    ],
)
@pytest.mark.parametrize("report_position_upon_stop", [True, False])
@pytest.mark.parametrize("command_successful", [True, False])
def test_execute_command(
    caplog,
    mac_address,
    password,
    retry_count,
    message_payload,
    action_name,
    report_position_upon_stop,
    command_successful,
):
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain.__init__", return_value=None
    ) as device_init_mock, caplog.at_level(logging.INFO):
        actor = switchbot_mqtt._CurtainMotor(
            mac_address=mac_address, retry_count=retry_count, password=password
        )
        with unittest.mock.patch.object(
            actor, "report_state"
        ) as report_mock, unittest.mock.patch(
            action_name, return_value=command_successful
        ) as action_mock, unittest.mock.patch.object(
            actor, "_update_position"
        ) as update_position_mock:
            actor.execute_command(
                mqtt_client="dummy",
                mqtt_message_payload=message_payload,
                update_device_info=report_position_upon_stop,
            )
    device_init_mock.assert_called_once_with(
        mac=mac_address, password=password, retry_count=retry_count, reverse_mode=True
    )
    action_mock.assert_called_once_with()
    if command_successful:
        assert caplog.record_tuples == [
            (
                "switchbot_mqtt",
                logging.INFO,
                "switchbot curtain {} {}".format(
                    mac_address,
                    {b"open": "opening", b"close": "closing", b"stop": "stopped"}[
                        message_payload.lower()
                    ],
                ),
            )
        ]
        report_mock.assert_called_once_with(
            mqtt_client="dummy",
            # https://www.home-assistant.io/integrations/cover.mqtt/#state_opening
            state={b"open": b"opening", b"close": b"closing", b"stop": b""}[
                message_payload.lower()
            ],
        )
    else:
        assert caplog.record_tuples == [
            (
                "switchbot_mqtt",
                logging.ERROR,
                "failed to {} switchbot curtain {}".format(
                    message_payload.decode().lower(), mac_address
                ),
            )
        ]
        report_mock.assert_not_called()
    if (
        report_position_upon_stop
        and action_name == "switchbot.SwitchbotCurtain.stop"
        and command_successful
    ):
        update_position_mock.assert_called_once_with(mqtt_client="dummy")
    else:
        update_position_mock.assert_not_called()


@pytest.mark.parametrize("mac_address", ["aa:bb:cc:dd:ee:ff"])
@pytest.mark.parametrize("password", ["secret"])
@pytest.mark.parametrize("message_payload", [b"OEFFNEN", b""])
def test_execute_command_invalid_payload(
    caplog, mac_address, password, message_payload
):
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain"
    ) as device_mock, caplog.at_level(logging.INFO):
        actor = switchbot_mqtt._CurtainMotor(
            mac_address=mac_address, retry_count=7, password=password
        )
        with unittest.mock.patch.object(actor, "report_state") as report_mock:
            actor.execute_command(
                mqtt_client="dummy",
                mqtt_message_payload=message_payload,
                update_device_info=True,
            )
    device_mock.assert_called_once_with(
        mac=mac_address, password=password, retry_count=7, reverse_mode=True
    )
    assert not device_mock().mock_calls  # no methods called
    report_mock.assert_not_called()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt",
            logging.WARNING,
            "unexpected payload {!r} (expected 'OPEN', 'CLOSE', or 'STOP')".format(
                message_payload
            ),
        )
    ]


@pytest.mark.parametrize("mac_address", ["aa:bb:cc:dd:ee:ff"])
@pytest.mark.parametrize("message_payload", [b"OPEN", b"CLOSE", b"STOP"])
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
        switchbot_mqtt._CurtainMotor(
            mac_address=mac_address, retry_count=10, password="secret"
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
            "failed to {} switchbot curtain {}".format(
                message_payload.decode().lower(), mac_address
            ),
        ),
    ]
