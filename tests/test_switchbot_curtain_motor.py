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

import _pytest.logging  # pylint: disable=import-private-name; typing
import pytest

# pylint: disable=import-private-name; internal
import switchbot_mqtt._utils
from switchbot_mqtt._actors import _CurtainMotor

# pylint: disable=protected-access,
# pylint: disable=too-many-arguments; these are tests, no API


@pytest.mark.parametrize("mac_address", ["{MAC_ADDRESS}", "aa:bb:cc:dd:ee:ff"])
def test_get_mqtt_battery_percentage_topic(mac_address: str) -> None:
    assert (
        _CurtainMotor.get_mqtt_battery_percentage_topic(
            prefix="homeassistant/", mac_address=mac_address
        )
        == f"homeassistant/cover/switchbot-curtain/{mac_address}/battery-percentage"
    )


@pytest.mark.parametrize("mac_address", ["{MAC_ADDRESS}", "aa:bb:cc:dd:ee:ff"])
def test_get_mqtt_position_topic(mac_address: str) -> None:
    assert (
        _CurtainMotor.get_mqtt_position_topic(prefix="prfx-", mac_address=mac_address)
        == f"prfx-cover/switchbot-curtain/{mac_address}/position"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mac_address",
    ("aa:bb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:gg"),
)
@pytest.mark.parametrize(
    ("position", "expected_payload"), [(0, b"0"), (100, b"100"), (42, b"42")]
)
async def test__report_position(
    caplog: _pytest.logging.LogCaptureFixture,
    mac_address: str,
    position: int,
    expected_payload: bytes,
) -> None:
    device = unittest.mock.Mock()
    device.address = mac_address
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain.__init__", return_value=None
    ) as device_init_mock, caplog.at_level(logging.DEBUG):
        actor = _CurtainMotor(device=device, retry_count=7, password=None)
    device_init_mock.assert_called_once_with(
        device=device,
        retry_count=7,
        password=None,
        # > The position of the curtain is saved in self._pos with 0 = open and 100 = closed.
        # > [...] The parameter 'reverse_mode' reverse these values, [...]
        # > The parameter is default set to True so that the definition of position
        # > is the same as in Home Assistant.
        # https://github.com/Danielhiversen/pySwitchbot/blob/0.10.0/switchbot/__init__.py#L150
        reverse_mode=True,
    )
    actor._basic_device_info = {"position": position}
    mqtt_client = unittest.mock.Mock()
    with unittest.mock.patch.object(actor, "_mqtt_publish") as publish_mock:
        await actor._report_position(
            mqtt_client=mqtt_client, mqtt_topic_prefix="topic-prefix"
        )
    publish_mock.assert_awaited_once_with(
        topic_prefix="topic-prefix",
        topic_levels=(
            "cover",
            "switchbot-curtain",
            switchbot_mqtt._utils._MQTTTopicPlaceholder.MAC_ADDRESS,
            "position",
        ),
        payload=expected_payload,
        mqtt_client=mqtt_client,
    )
    assert not caplog.record_tuples


@pytest.mark.asyncio
@pytest.mark.parametrize("position", ("", 'lambda: print("")'))
async def test__report_position_invalid(
    caplog: _pytest.logging.LogCaptureFixture, position: str
) -> None:
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain.__init__", return_value=None
    ), caplog.at_level(logging.DEBUG):
        actor = _CurtainMotor(device=unittest.mock.Mock(), retry_count=3, password=None)
    actor._basic_device_info = {"position": position}
    with unittest.mock.patch.object(
        actor, "_mqtt_publish"
    ) as publish_mock, pytest.raises(ValueError):
        await actor._report_position(
            mqtt_client=unittest.mock.Mock(), mqtt_topic_prefix="dummy2"
        )
    publish_mock.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("topic_prefix", ["", "homeassistant/"])
@pytest.mark.parametrize(("battery_percent", "battery_percent_encoded"), [(42, b"42")])
@pytest.mark.parametrize("report_position", [True, False])
@pytest.mark.parametrize(("position", "position_encoded"), [(21, b"21")])
async def test__update_and_report_device_info(
    topic_prefix: str,
    report_position: bool,
    battery_percent: int,
    battery_percent_encoded: bytes,
    position: int,
    position_encoded: bytes,
) -> None:
    device = unittest.mock.Mock()
    device.address = "dummy"
    with unittest.mock.patch("switchbot.SwitchbotCurtain.__init__", return_value=None):
        actor = _CurtainMotor(device=device, retry_count=21, password=None)
    mqtt_client_mock = unittest.mock.AsyncMock()
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain.get_basic_info",
        return_value={"battery": battery_percent, "position": position},
    ) as update_mock:
        await actor._update_and_report_device_info(
            mqtt_client=mqtt_client_mock,
            mqtt_topic_prefix=topic_prefix,
            report_position=report_position,
        )
    update_mock.assert_called_once_with()
    assert mqtt_client_mock.publish.await_count == (1 + report_position)
    assert (
        unittest.mock.call(
            topic=topic_prefix + "cover/switchbot-curtain/dummy/battery-percentage",
            payload=battery_percent_encoded,
            retain=True,
        )
        in mqtt_client_mock.publish.await_args_list
    )
    if report_position:
        assert (
            unittest.mock.call(
                topic=topic_prefix + "cover/switchbot-curtain/dummy/position",
                payload=position_encoded,
                retain=True,
            )
            in mqtt_client_mock.publish.await_args_list
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("mac_address", ["aa:bb:cc:dd:ee:ff", "aa:bb:cc:11:22:33"])
async def test__update_and_report_device_info_get_basic_info_failed(
    caplog: _pytest.logging.LogCaptureFixture, mac_address: str
) -> None:
    device = unittest.mock.Mock()
    device.address = mac_address
    actor = _CurtainMotor(device=device, retry_count=21, password=None)
    mqtt_client_mock = unittest.mock.MagicMock()
    # https://github.com/Danielhiversen/pySwitchbot/blob/0.40.1/switchbot/devices/curtain.py#L96
    with unittest.mock.patch.object(
        actor._get_device(), "get_basic_info", return_value=None
    ), caplog.at_level(logging.DEBUG):
        await actor._update_and_report_device_info(
            mqtt_client_mock, mqtt_topic_prefix="dummy", report_position=True
        )
    mqtt_client_mock.publish.assert_not_called()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors.base",
            logging.ERROR,
            f"failed to retrieve basic device info from {mac_address}",
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("topic_prefix", ["topic-prfx"])
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
@pytest.mark.parametrize("update_device_info", [True, False])
@pytest.mark.parametrize("command_successful", [True, False])
async def test_execute_command(
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
    # pylint: disable=too-many-locals
    device = unittest.mock.Mock()
    device.address = mac_address
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain.__init__", return_value=None
    ) as device_init_mock, caplog.at_level(logging.INFO):
        actor = _CurtainMotor(device=device, retry_count=retry_count, password=password)
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
        device=device, password=password, retry_count=retry_count, reverse_mode=True
    )
    action_mock.assert_called_once_with()
    if command_successful:
        state_str = {b"open": "opening", b"close": "closing", b"stop": "stopped"}[
            message_payload.lower()
        ]
        assert caplog.record_tuples == [
            (
                "switchbot_mqtt._actors",
                logging.INFO,
                f"switchbot curtain {mac_address} {state_str}",
            )
        ]
        report_mock.assert_awaited_once_with(
            mqtt_client=mqtt_client,
            mqtt_topic_prefix=topic_prefix,
            # https://www.home-assistant.io/integrations/cover.mqtt/#state_opening
            state={b"open": b"opening", b"close": b"closing", b"stop": b""}[
                message_payload.lower()
            ],
        )
    else:
        assert caplog.record_tuples == [
            (
                "switchbot_mqtt._actors",
                logging.ERROR,
                f"failed to {message_payload.decode().lower()} switchbot curtain {mac_address}",
            )
        ]
        report_mock.assert_not_called()
    if update_device_info and command_successful:
        update_device_info_mock.assert_awaited_once_with(
            mqtt_client=mqtt_client,
            report_position=(action_name == "switchbot.SwitchbotCurtain.stop"),
            mqtt_topic_prefix=topic_prefix,
        )
    else:
        update_device_info_mock.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("password", ["secret"])
@pytest.mark.parametrize("message_payload", [b"OEFFNEN", b""])
async def test_execute_command_invalid_payload(
    caplog: _pytest.logging.LogCaptureFixture, password: str, message_payload: bytes
) -> None:
    device = unittest.mock.Mock()
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain"
    ) as device_mock, caplog.at_level(logging.INFO):
        actor = _CurtainMotor(device=device, retry_count=7, password=password)
        with unittest.mock.patch.object(actor, "report_state") as report_mock:
            await actor.execute_command(
                mqtt_client=unittest.mock.Mock(),
                mqtt_message_payload=message_payload,
                update_device_info=True,
                mqtt_topic_prefix="dummy",
            )
    device_mock.assert_called_once_with(
        device=device, password=password, retry_count=7, reverse_mode=True
    )
    assert not device_mock().mock_calls  # no methods called
    report_mock.assert_not_called()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors",
            logging.WARNING,
            f"unexpected payload {message_payload!r} (expected 'OPEN', 'CLOSE', or 'STOP')",
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("mac_address", ["aa:bb:cc:dd:ee:ff"])
@pytest.mark.parametrize(
    ("message_payload", "action"),
    [
        (b"OPEN", "switchbot.SwitchbotCurtain.open"),
        (b"CLOSE", "switchbot.SwitchbotCurtain.close"),
        (b"STOP", "switchbot.SwitchbotCurtain.stop"),
    ],
)
async def test_execute_command_failed(
    caplog: _pytest.logging.LogCaptureFixture,
    mac_address: str,
    message_payload: bytes,
    action: str,
) -> None:
    device = unittest.mock.Mock()
    device.address = mac_address
    with unittest.mock.patch(action, return_value=False), caplog.at_level(
        logging.ERROR
    ):
        await _CurtainMotor(
            device=device, retry_count=0, password="secret"
        ).execute_command(
            mqtt_client=unittest.mock.Mock(),
            mqtt_message_payload=message_payload,
            update_device_info=True,
            mqtt_topic_prefix="dummy",
        )
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors",
            logging.ERROR,
            f"failed to {message_payload.decode().lower()} switchbot curtain {mac_address}",
        )
    ]
