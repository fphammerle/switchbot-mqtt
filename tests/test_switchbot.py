import logging
import unittest.mock

import bluepy.btle
import pytest

import switchbot_mqtt

# pylint: disable=protected-access


@pytest.mark.parametrize("mac_address", ["aa:bb:cc:dd:ee:ff"])
@pytest.mark.parametrize(
    "action", [switchbot_mqtt._SwitchbotAction.ON, switchbot_mqtt._SwitchbotAction.OFF]
)
@pytest.mark.parametrize("command_successful", [True, False])
def test__send_command(caplog, mac_address, action, command_successful):
    with unittest.mock.patch("switchbot.Switchbot") as switchbot_device_mock:
        switchbot_device_mock().turn_on.return_value = command_successful
        switchbot_device_mock().turn_off.return_value = command_successful
        switchbot_device_mock.reset_mock()
        with unittest.mock.patch("switchbot_mqtt._report_state") as report_mock:
            with caplog.at_level(logging.INFO):
                switchbot_mqtt._send_command(
                    mqtt_client="dummy",
                    switchbot_mac_address=mac_address,
                    action=action,
                )
    switchbot_device_mock.assert_called_once_with(mac=mac_address)
    assert len(caplog.records) == 1
    logger, log_level, log_message = caplog.record_tuples[0]
    assert logger == "switchbot_mqtt"
    if command_successful:
        assert log_level == logging.INFO
    else:
        assert log_level == logging.ERROR
        assert "failed" in log_message
    assert mac_address in log_message
    if action == switchbot_mqtt._SwitchbotAction.ON:
        switchbot_device_mock().turn_on.assert_called_once_with()
        assert not switchbot_device_mock().turn_off.called
        assert "on" in log_message
        expected_state = switchbot_mqtt._SwitchbotState.ON
    else:
        switchbot_device_mock().turn_off.assert_called_once_with()
        assert not switchbot_device_mock().turn_on.called
        assert "off" in log_message
        expected_state = switchbot_mqtt._SwitchbotState.OFF
    assert report_mock.called == command_successful
    if command_successful:
        report_mock.assert_called_once_with(
            mqtt_client="dummy",
            switchbot_mac_address=mac_address,
            switchbot_state=expected_state,
        )


@pytest.mark.parametrize("mac_address", ["aa:bb:cc:dd:ee:ff"])
@pytest.mark.parametrize("action", [switchbot_mqtt._SwitchbotAction.ON])
def test__send_command_bluetooth_error(caplog, mac_address, action):
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
        switchbot_mqtt._send_command(
            mqtt_client=None, switchbot_mac_address=mac_address, action=action
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
            "failed to turn on switchbot {}".format(mac_address),
        ),
    ]
