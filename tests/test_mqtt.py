import unittest.mock

import pytest

import switchbot_mqtt


@pytest.mark.parametrize("mqtt_host", ["mqtt-broker.local"])
@pytest.mark.parametrize("mqtt_port", [1833])
def test__run(mqtt_host, mqtt_port):
    with unittest.mock.patch(
        "paho.mqtt.client.Client"
    ) as mqtt_client_mock, unittest.mock.patch(
        "switchbot_mqtt._mqtt_on_message"
    ) as message_handler_mock:
        # pylint: disable=protected-access
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
