# switchbot-mqtt - MQTT client controlling SwitchBot button & curtain automators,
# compatible with home-assistant.io's MQTT Switch & Cover platform
#
# Copyright (C) 2021 Fabian Peter Hammerle <fabian@hammerle.me>
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

import os
import re
import unittest.mock

import bluepy.btle
import pytest
import switchbot_mqtt

# pylint: disable=protected-access

_LE_ON_PERMISSION_DENIED_ERROR = bluepy.btle.BTLEManagementError(
    "Failed to execute management command 'le on'",
    {
        "rsp": ["mgmt"],
        "code": ["mgmterr"],
        "estat": [20],
        "emsg": ["Permission Denied"],
    },
)


def test__update_position_le_on_permission_denied_log():  # pySwitchbot>=v0.10.0
    actor = switchbot_mqtt._CurtainMotor(
        mac_address="dummy", retry_count=21, password=None
    )
    with unittest.mock.patch(
        "bluepy.btle.Scanner.scan",
        side_effect=_LE_ON_PERMISSION_DENIED_ERROR,
    ), unittest.mock.patch.object(
        actor, "_report_position"
    ) as report_position_mock, pytest.raises(
        PermissionError
    ) as exc_info:
        actor._update_position(mqtt_client="client")
    report_position_mock.assert_not_called()
    assert "sudo setcap cap_net_admin+ep /" in exc_info.exconly()
    assert exc_info.value.__cause__ == _LE_ON_PERMISSION_DENIED_ERROR


def test__update_position_le_on_permission_denied_exc():  # pySwitchbot<v0.10.1
    actor = switchbot_mqtt._CurtainMotor(
        mac_address="dummy", retry_count=21, password=None
    )
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain.update",
        side_effect=_LE_ON_PERMISSION_DENIED_ERROR,
    ) as update_mock, unittest.mock.patch.object(
        actor, "_report_position"
    ) as report_position_mock, pytest.raises(
        PermissionError
    ) as exc_info:
        actor._update_position(mqtt_client="client")
    update_mock.assert_called_once_with()
    report_position_mock.assert_not_called()
    assert os.path.isfile(
        re.search(
            r"sudo setcap cap_net_admin\+ep (\S+/bluepy-helper)\b",
            exc_info.exconly(),
        ).group(1)
    )
    assert exc_info.value.__cause__ == _LE_ON_PERMISSION_DENIED_ERROR


def test__update_position_other_error():
    actor = switchbot_mqtt._CurtainMotor(
        mac_address="dummy", retry_count=21, password=None
    )
    side_effect = bluepy.btle.BTLEManagementError("test")
    with unittest.mock.patch(
        "switchbot.SwitchbotCurtain.update", side_effect=side_effect
    ) as update_mock, unittest.mock.patch.object(
        actor, "_report_position"
    ) as report_position_mock, pytest.raises(
        type(side_effect)
    ) as exc_info:
        actor._update_position(mqtt_client="client")
    update_mock.assert_called_once_with()
    report_position_mock.assert_not_called()
    assert exc_info.value == side_effect
