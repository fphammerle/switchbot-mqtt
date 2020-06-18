import logging
import unittest.mock

import pytest
from paho.mqtt.client import MQTT_ERR_QUEUE_SIZE, MQTT_ERR_SUCCESS, MQTTMessage

import switchbot_mqtt

# pylint: disable=protected-access


@pytest.mark.parametrize("mqtt_host", ["mqtt-broker.local"])
@pytest.mark.parametrize("mqtt_port", [1833])
def test__run(mqtt_host, mqtt_port):
    with unittest.mock.patch(
        "paho.mqtt.client.Client"
    ) as mqtt_client_mock, unittest.mock.patch(
        "switchbot_mqtt._mqtt_on_message"
    ) as message_handler_mock:
        switchbot_mqtt._run(
            mqtt_host=mqtt_host,
            mqtt_port=mqtt_port,
            mqtt_username=None,
            mqtt_password=None,
        )
    mqtt_client_mock.assert_called_once_with()
    assert not mqtt_client_mock().username_pw_set.called
    mqtt_client_mock().connect.assert_called_once_with(host=mqtt_host, port=mqtt_port)
    mqtt_client_mock().socket().getpeername.return_value = (mqtt_host, mqtt_port)
    mqtt_client_mock().on_connect(mqtt_client_mock(), None, {}, 0)
    mqtt_client_mock().subscribe.assert_called_once_with(
        "homeassistant/switch/switchbot/+/set"
    )
    mqtt_client_mock().on_message(mqtt_client_mock(), None, "message")
    # assert_called_once new in python3.6
    assert message_handler_mock.call_count == 1
    mqtt_client_mock().loop_forever.assert_called_once_with()


@pytest.mark.parametrize("mqtt_host", ["mqtt-broker.local"])
@pytest.mark.parametrize("mqtt_port", [1833])
@pytest.mark.parametrize("mqtt_username", ["me"])
@pytest.mark.parametrize("mqtt_password", [None, "secret"])
def test__run_authentication(mqtt_host, mqtt_port, mqtt_username, mqtt_password):
    with unittest.mock.patch("paho.mqtt.client.Client") as mqtt_client_mock:
        switchbot_mqtt._run(
            mqtt_host=mqtt_host,
            mqtt_port=mqtt_port,
            mqtt_username=mqtt_username,
            mqtt_password=mqtt_password,
        )
    mqtt_client_mock.assert_called_once_with()
    mqtt_client_mock().username_pw_set.assert_called_once_with(
        username=mqtt_username, password=mqtt_password,
    )


@pytest.mark.parametrize("mqtt_host", ["mqtt-broker.local"])
@pytest.mark.parametrize("mqtt_port", [1833])
@pytest.mark.parametrize("mqtt_password", ["secret"])
def test__run_authentication_missing_username(mqtt_host, mqtt_port, mqtt_password):
    with unittest.mock.patch("paho.mqtt.client.Client"):
        with pytest.raises(ValueError):
            switchbot_mqtt._run(
                mqtt_host=mqtt_host,
                mqtt_port=mqtt_port,
                mqtt_username=None,
                mqtt_password=mqtt_password,
            )


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
        switchbot_mqtt._mqtt_on_message("client_dummy", None, message)
    send_command_mock.assert_called_once_with(
        mqtt_client="client_dummy",
        switchbot_mac_address=expected_mac_address,
        action=expected_action,
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


@pytest.mark.parametrize(
    ("switchbot_mac_address", "expected_topic"),
    # https://www.home-assistant.io/docs/mqtt/discovery/#switches
    [("aa:bb:cc:dd:ee:ff", "homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/state")],
)
@pytest.mark.parametrize(
    ("state", "expected_payload"),
    [
        (switchbot_mqtt._SwitchbotState.ON, b"ON"),
        (switchbot_mqtt._SwitchbotState.OFF, b"OFF"),
    ],
)
@pytest.mark.parametrize(
    "return_code", [MQTT_ERR_SUCCESS, MQTT_ERR_QUEUE_SIZE],
)
def test__report_state(
    caplog,
    state: switchbot_mqtt._SwitchbotState,
    switchbot_mac_address: str,
    expected_topic: str,
    expected_payload: bytes,
    return_code: int,
):
    # pylint: disable=too-many-arguments
    mqtt_client_mock = unittest.mock.MagicMock()
    mqtt_client_mock.publish.return_value.rc = return_code
    with caplog.at_level(logging.WARNING):
        switchbot_mqtt._report_state(
            mqtt_client=mqtt_client_mock,
            switchbot_mac_address=switchbot_mac_address,
            switchbot_state=state,
        )
    mqtt_client_mock.publish.assert_called_once_with(
        topic=expected_topic, payload=expected_payload, retain=True,
    )
    if return_code == MQTT_ERR_SUCCESS:
        assert len(caplog.records) == 0
    else:
        assert len(caplog.records) == 1
        assert caplog.record_tuples[0] == (
            "switchbot_mqtt",
            logging.ERROR,
            "failed to publish state (rc={})".format(return_code),
        )
