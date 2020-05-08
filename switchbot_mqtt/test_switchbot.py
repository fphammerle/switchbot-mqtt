import unittest.mock

import pytest

import switchbot_mqtt

# pylint: disable=protected-access


@pytest.mark.parametrize("mac_address", ["aa:bb:cc:dd:ee:ff"])
@pytest.mark.parametrize(
    "action", [switchbot_mqtt._SwitchbotAction.ON, switchbot_mqtt._SwitchbotAction.OFF]
)
def test__send_command(mac_address, action):
    with unittest.mock.patch("switchbot.Switchbot") as switchbot_device_mock:
        switchbot_device_mock.turn_on = unittest.mock.MagicMock(return_value=True)
        switchbot_device_mock.turn_off = unittest.mock.MagicMock(return_value=True)
        switchbot_mqtt._send_command(mac_address, action)
    switchbot_device_mock.assert_called_once_with(mac=mac_address)
    if action == switchbot_mqtt._SwitchbotAction.ON:
        switchbot_device_mock().turn_on.assert_called_once_with()
        assert not switchbot_device_mock().turn_off.called
    else:
        switchbot_device_mock().turn_off.assert_called_once_with()
        assert not switchbot_device_mock().turn_on.called
