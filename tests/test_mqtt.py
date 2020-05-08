import unittest.mock

import pytest

import switchbot_mqtt
from paho.mqtt.client import MQTTMessage

# pylint: disable=protected-access


@pytest.mark.parametrize("mqtt_host", ["mqtt-broker.local"])
@pytest.mark.parametrize("mqtt_port", [1833])
def test__run(mqtt_host, mqtt_port):
    with unittest.mock.patch(
        "paho.mqtt.client.Client"
    ) as mqtt_client_mock, unittest.mock.patch(
        "switchbot_mqtt._mqtt_on_message"
    ) as message_handler_mock:
        switchbot_mqtt._run(mqtt_host=mqtt_host, mqtt_port=mqtt_port)
    mqtt_client_mock.assert_called_once_with()
    mqtt_client_mock().connect.assert_called_once_with(host=mqtt_host, port=mqtt_port)
    mqtt_client_mock().socket().getpeername.return_value = (mqtt_host, mqtt_port)
    mqtt_client_mock().on_connect(mqtt_client_mock(), None, {}, 0)
    mqtt_client_mock().subscribe.assert_called_once_with(
        "homeassistant/switch/switchbot/+/set"
    )
    mqtt_client_mock().on_message(mqtt_client_mock(), None, "message")
    message_handler_mock.assert_called_once()
    mqtt_client_mock().loop_forever.assert_called_once_with()


@pytest.mark.parametrize(
    ("topic", "payload", "expected_mac_address", "expected_action"),
    [
        (
            b"homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set",
            b"ON",
            "aa:bb:cc:dd:ee:ff",
            switchbot_mqtt._SwitchbotAction.ON,
        ),
        (
            b"homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set",
            b"OFF",
            "aa:bb:cc:dd:ee:ff",
            switchbot_mqtt._SwitchbotAction.OFF,
        ),
        (
            b"homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set",
            b"on",
            "aa:bb:cc:dd:ee:ff",
            switchbot_mqtt._SwitchbotAction.ON,
        ),
        (
            b"homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set",
            b"off",
            "aa:bb:cc:dd:ee:ff",
            switchbot_mqtt._SwitchbotAction.OFF,
        ),
        (
            b"homeassistant/switch/switchbot/aa:01:23:45:67:89/set",
            b"ON",
            "aa:01:23:45:67:89",
            switchbot_mqtt._SwitchbotAction.ON,
        ),
    ],
)
def test__mqtt_on_message(
    topic: bytes,
    payload: bytes,
    expected_mac_address: str,
    expected_action: switchbot_mqtt._SwitchbotAction,
):
    message = MQTTMessage(topic=topic)
    message.payload = payload
    with unittest.mock.patch("switchbot_mqtt._send_command") as send_command_mock:
        switchbot_mqtt._mqtt_on_message(None, None, message)
    send_command_mock.assert_called_once_with(
        switchbot_mac_address=expected_mac_address, action=expected_action
    )


@pytest.mark.parametrize(
    ("topic", "payload"),
    [
        (b"homeassistant/switch/switchbot/aa:01:23:4E:RR:OR/set", b"ON"),
        (b"homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff", b"on"),
        (b"homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/change", b"ON"),
        (b"homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set", b""),
        (b"homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set", b"EIN"),
    ],
)
def test__mqtt_on_message_ignored(
    topic: bytes, payload: bytes,
):
    message = MQTTMessage(topic=topic)
    message.payload = payload
    with unittest.mock.patch("switchbot_mqtt._send_command") as send_command_mock:
        switchbot_mqtt._mqtt_on_message(None, None, message)
    assert not send_command_mock.called


@pytest.mark.parametrize(
    ("topic", "payload"),
    [(b"homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set", b"ON")],
)
def test__mqtt_on_message_ignored_retained(
    topic: bytes, payload: bytes,
):
    message = MQTTMessage(topic=topic)
    message.payload = payload
    message.retain = True
    with unittest.mock.patch("switchbot_mqtt._send_command") as send_command_mock:
        switchbot_mqtt._mqtt_on_message(None, None, message)
    assert not send_command_mock.called
