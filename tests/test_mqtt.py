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
import pytest
from paho.mqtt.client import MQTT_ERR_QUEUE_SIZE, MQTT_ERR_SUCCESS, MQTTMessage, Client

import switchbot_mqtt
import switchbot_mqtt._actors
from switchbot_mqtt._actors import _ButtonAutomator, _CurtainMotor
from switchbot_mqtt._actors.base import _MQTTCallbackUserdata, _MQTTControlledActor
from switchbot_mqtt._utils import _MQTTTopicLevel, _MQTTTopicPlaceholder

# pylint: disable=protected-access
# pylint: disable=too-many-arguments; these are tests, no API


@pytest.mark.parametrize("mqtt_host", ["mqtt-broker.local"])
@pytest.mark.parametrize("mqtt_port", [1833])
@pytest.mark.parametrize("retry_count", [3, 21])
@pytest.mark.parametrize(
    "device_passwords",
    [{}, {"11:22:33:44:55:66": "password", "aa:bb:cc:dd:ee:ff": "secret"}],
)
@pytest.mark.parametrize("fetch_device_info", [True, False])
def test__run(
    caplog: _pytest.logging.LogCaptureFixture,
    mqtt_host: str,
    mqtt_port: int,
    retry_count: int,
    device_passwords: typing.Dict[str, str],
    fetch_device_info: bool,
) -> None:
    with unittest.mock.patch(
        "paho.mqtt.client.Client"
    ) as mqtt_client_mock, caplog.at_level(logging.DEBUG):
        switchbot_mqtt._run(
            mqtt_host=mqtt_host,
            mqtt_port=mqtt_port,
            mqtt_disable_tls=False,
            mqtt_username=None,
            mqtt_password=None,
            mqtt_topic_prefix="homeassistant/",
            retry_count=retry_count,
            device_passwords=device_passwords,
            fetch_device_info=fetch_device_info,
        )
    mqtt_client_mock.assert_called_once()
    assert not mqtt_client_mock.call_args[0]
    assert set(mqtt_client_mock.call_args[1].keys()) == {"userdata"}
    userdata = mqtt_client_mock.call_args[1]["userdata"]
    assert userdata == _MQTTCallbackUserdata(
        retry_count=retry_count,
        device_passwords=device_passwords,
        fetch_device_info=fetch_device_info,
        mqtt_topic_prefix="homeassistant/",
    )
    assert not mqtt_client_mock().username_pw_set.called
    mqtt_client_mock().tls_set.assert_called_once_with(ca_certs=None)
    mqtt_client_mock().connect.assert_called_once_with(host=mqtt_host, port=mqtt_port)
    mqtt_client_mock().socket().getpeername.return_value = (mqtt_host, mqtt_port)
    with caplog.at_level(logging.DEBUG):
        mqtt_client_mock().on_connect(mqtt_client_mock(), userdata, {}, 0)
    subscribe_mock = mqtt_client_mock().subscribe
    assert subscribe_mock.call_count == (5 if fetch_device_info else 3)
    for topic in [
        "homeassistant/switch/switchbot/+/set",
        "homeassistant/cover/switchbot-curtain/+/set",
        "homeassistant/cover/switchbot-curtain/+/position/set-percent",
    ]:
        assert unittest.mock.call(topic) in subscribe_mock.call_args_list
    for topic in [
        "homeassistant/switch/switchbot/+/request-device-info",
        "homeassistant/cover/switchbot-curtain/+/request-device-info",
    ]:
        assert (
            unittest.mock.call(topic) in subscribe_mock.call_args_list
        ) == fetch_device_info
    callbacks = {
        c[1]["sub"]: c[1]["callback"]
        for c in mqtt_client_mock().message_callback_add.call_args_list
    }
    assert (  # pylint: disable=comparison-with-callable; intended
        callbacks["homeassistant/cover/switchbot-curtain/+/position/set-percent"]
        == _CurtainMotor._mqtt_set_position_callback
    )
    mqtt_client_mock().loop_forever.assert_called_once_with()
    assert caplog.record_tuples[:2] == [
        (
            "switchbot_mqtt",
            logging.INFO,
            f"connecting to MQTT broker {mqtt_host}:{mqtt_port} (TLS enabled)",
        ),
        (
            "switchbot_mqtt",
            logging.DEBUG,
            f"connected to MQTT broker {mqtt_host}:{mqtt_port}",
        ),
    ]
    assert len(caplog.record_tuples) == (7 if fetch_device_info else 5)
    assert (
        "switchbot_mqtt._actors.base",
        logging.INFO,
        "subscribing to MQTT topic 'homeassistant/switch/switchbot/+/set'",
    ) in caplog.record_tuples
    assert (
        "switchbot_mqtt._actors.base",
        logging.INFO,
        "subscribing to MQTT topic 'homeassistant/cover/switchbot-curtain/+/set'",
    ) in caplog.record_tuples


@pytest.mark.parametrize("mqtt_disable_tls", [True, False])
def test__run_tls(
    caplog: _pytest.logging.LogCaptureFixture, mqtt_disable_tls: bool
) -> None:
    with unittest.mock.patch(
        "paho.mqtt.client.Client"
    ) as mqtt_client_mock, caplog.at_level(logging.INFO):
        switchbot_mqtt._run(
            mqtt_host="mqtt.local",
            mqtt_port=1234,
            mqtt_disable_tls=mqtt_disable_tls,
            mqtt_username=None,
            mqtt_password=None,
            mqtt_topic_prefix="prfx",
            retry_count=21,
            device_passwords={},
            fetch_device_info=True,
        )
    if mqtt_disable_tls:
        mqtt_client_mock().tls_set.assert_not_called()
    else:
        mqtt_client_mock().tls_set.assert_called_once_with(ca_certs=None)
    if mqtt_disable_tls:
        assert caplog.record_tuples[0][2].endswith(" (TLS disabled)")
    else:
        assert caplog.record_tuples[0][2].endswith(" (TLS enabled)")


@pytest.mark.parametrize("mqtt_host", ["mqtt-broker.local"])
@pytest.mark.parametrize("mqtt_port", [1833])
@pytest.mark.parametrize("mqtt_username", ["me"])
@pytest.mark.parametrize("mqtt_password", [None, "secret"])
def test__run_authentication(
    mqtt_host: str,
    mqtt_port: int,
    mqtt_username: str,
    mqtt_password: typing.Optional[str],
) -> None:
    with unittest.mock.patch("paho.mqtt.client.Client") as mqtt_client_mock:
        switchbot_mqtt._run(
            mqtt_host=mqtt_host,
            mqtt_port=mqtt_port,
            mqtt_disable_tls=True,
            mqtt_username=mqtt_username,
            mqtt_password=mqtt_password,
            mqtt_topic_prefix="prfx",
            retry_count=7,
            device_passwords={},
            fetch_device_info=True,
        )
    mqtt_client_mock.assert_called_once_with(
        userdata=_MQTTCallbackUserdata(
            retry_count=7,
            device_passwords={},
            fetch_device_info=True,
            mqtt_topic_prefix="prfx",
        )
    )
    mqtt_client_mock().username_pw_set.assert_called_once_with(
        username=mqtt_username, password=mqtt_password
    )


@pytest.mark.parametrize("mqtt_host", ["mqtt-broker.local"])
@pytest.mark.parametrize("mqtt_port", [1833])
@pytest.mark.parametrize("mqtt_password", ["secret"])
def test__run_authentication_missing_username(
    mqtt_host: str, mqtt_port: int, mqtt_password: str
) -> None:
    with unittest.mock.patch("paho.mqtt.client.Client"):
        with pytest.raises(ValueError):
            switchbot_mqtt._run(
                mqtt_host=mqtt_host,
                mqtt_port=mqtt_port,
                mqtt_disable_tls=True,
                mqtt_username=None,
                mqtt_password=mqtt_password,
                mqtt_topic_prefix="whatever",
                retry_count=3,
                device_passwords={},
                fetch_device_info=True,
            )


def _mock_actor_class(
    *,
    command_topic_levels: typing.Tuple[_MQTTTopicLevel, ...] = NotImplemented,
    request_info_levels: typing.Tuple[_MQTTTopicLevel, ...] = NotImplemented,
) -> typing.Type:
    class _ActorMock(_MQTTControlledActor):
        MQTT_COMMAND_TOPIC_LEVELS = command_topic_levels
        _MQTT_UPDATE_DEVICE_INFO_TOPIC_LEVELS = request_info_levels

        def __init__(
            self, mac_address: str, retry_count: int, password: typing.Optional[str]
        ) -> None:
            super().__init__(
                mac_address=mac_address, retry_count=retry_count, password=password
            )

        def execute_command(
            self,
            *,
            mqtt_message_payload: bytes,
            mqtt_client: Client,
            update_device_info: bool,
            mqtt_topic_prefix: str,
        ) -> None:
            pass

        def _get_device(self) -> None:
            return None

    return _ActorMock


@pytest.mark.parametrize(
    ("topic_levels", "topic", "expected_mac_address"),
    [
        (
            switchbot_mqtt._actors._ButtonAutomator._MQTT_UPDATE_DEVICE_INFO_TOPIC_LEVELS,
            b"prfx/switch/switchbot/aa:bb:cc:dd:ee:ff/request-device-info",
            "aa:bb:cc:dd:ee:ff",
        ),
    ],
)
@pytest.mark.parametrize("payload", [b"", b"whatever"])
def test__mqtt_update_device_info_callback(
    caplog: _pytest.logging.LogCaptureFixture,
    topic_levels: typing.Tuple[_MQTTTopicLevel, ...],
    topic: bytes,
    expected_mac_address: str,
    payload: bytes,
) -> None:
    ActorMock = _mock_actor_class(request_info_levels=topic_levels)
    message = MQTTMessage(topic=topic)
    message.payload = payload
    callback_userdata = _MQTTCallbackUserdata(
        retry_count=21,  # tested in test__mqtt_command_callback
        device_passwords={},
        fetch_device_info=True,
        mqtt_topic_prefix="prfx/",
    )
    with unittest.mock.patch.object(
        ActorMock, "__init__", return_value=None
    ) as init_mock, unittest.mock.patch.object(
        ActorMock, "_update_and_report_device_info"
    ) as update_mock, caplog.at_level(
        logging.DEBUG
    ):
        ActorMock._mqtt_update_device_info_callback(
            "client_dummy", callback_userdata, message
        )
    init_mock.assert_called_once_with(
        mac_address=expected_mac_address, retry_count=21, password=None
    )
    update_mock.assert_called_once_with(
        mqtt_client="client_dummy", mqtt_topic_prefix="prfx/"
    )
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors.base",
            logging.DEBUG,
            f"received topic={topic.decode()} payload={payload!r}",
        )
    ]


def test__mqtt_update_device_info_callback_ignore_retained(
    caplog: _pytest.logging.LogCaptureFixture,
) -> None:
    ActorMock = _mock_actor_class(
        request_info_levels=(_MQTTTopicPlaceholder.MAC_ADDRESS, "request")
    )
    message = MQTTMessage(topic=b"aa:bb:cc:dd:ee:ff/request")
    message.payload = b""
    message.retain = True
    with unittest.mock.patch.object(
        ActorMock, "__init__", return_value=None
    ) as init_mock, unittest.mock.patch.object(
        ActorMock, "execute_command"
    ) as execute_command_mock, caplog.at_level(
        logging.DEBUG
    ):
        ActorMock._mqtt_update_device_info_callback(
            "client_dummy",
            _MQTTCallbackUserdata(
                retry_count=21,
                device_passwords={},
                fetch_device_info=True,
                mqtt_topic_prefix="ignored",
            ),
            message,
        )
    init_mock.assert_not_called()
    execute_command_mock.assert_not_called()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors.base",
            logging.DEBUG,
            "received topic=aa:bb:cc:dd:ee:ff/request payload=b''",
        ),
        ("switchbot_mqtt._actors.base", logging.INFO, "ignoring retained message"),
    ]


@pytest.mark.parametrize(
    (
        "topic_prefix",
        "command_topic_levels",
        "topic",
        "payload",
        "expected_mac_address",
    ),
    [
        (
            "homeassistant/",
            _ButtonAutomator.MQTT_COMMAND_TOPIC_LEVELS,
            b"homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set",
            b"ON",
            "aa:bb:cc:dd:ee:ff",
        ),
        (
            "homeassistant/",
            _ButtonAutomator.MQTT_COMMAND_TOPIC_LEVELS,
            b"homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set",
            b"OFF",
            "aa:bb:cc:dd:ee:ff",
        ),
        (
            "homeassistant/",
            _ButtonAutomator.MQTT_COMMAND_TOPIC_LEVELS,
            b"homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set",
            b"on",
            "aa:bb:cc:dd:ee:ff",
        ),
        (
            "homeassistant/",
            _ButtonAutomator.MQTT_COMMAND_TOPIC_LEVELS,
            b"homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set",
            b"off",
            "aa:bb:cc:dd:ee:ff",
        ),
        (
            "prefix-",
            _ButtonAutomator.MQTT_COMMAND_TOPIC_LEVELS,
            b"prefix-switch/switchbot/aa:01:23:45:67:89/set",
            b"ON",
            "aa:01:23:45:67:89",
        ),
        (
            "",
            ["switchbot", _MQTTTopicPlaceholder.MAC_ADDRESS],
            b"switchbot/aa:01:23:45:67:89",
            b"ON",
            "aa:01:23:45:67:89",
        ),
        (
            "homeassistant/",
            _CurtainMotor.MQTT_COMMAND_TOPIC_LEVELS,
            b"homeassistant/cover/switchbot-curtain/aa:01:23:45:67:89/set",
            b"OPEN",
            "aa:01:23:45:67:89",
        ),
    ],
)
@pytest.mark.parametrize("retry_count", (3, 42))
@pytest.mark.parametrize("fetch_device_info", [True, False])
def test__mqtt_command_callback(
    caplog: _pytest.logging.LogCaptureFixture,
    topic_prefix: str,
    command_topic_levels: typing.Tuple[_MQTTTopicLevel, ...],
    topic: bytes,
    payload: bytes,
    expected_mac_address: str,
    retry_count: int,
    fetch_device_info: bool,
) -> None:
    ActorMock = _mock_actor_class(command_topic_levels=command_topic_levels)
    message = MQTTMessage(topic=topic)
    message.payload = payload
    callback_userdata = _MQTTCallbackUserdata(
        retry_count=retry_count,
        device_passwords={},
        fetch_device_info=fetch_device_info,
        mqtt_topic_prefix=topic_prefix,
    )
    with unittest.mock.patch.object(
        ActorMock, "__init__", return_value=None
    ) as init_mock, unittest.mock.patch.object(
        ActorMock, "execute_command"
    ) as execute_command_mock, caplog.at_level(
        logging.DEBUG
    ):
        ActorMock._mqtt_command_callback("client_dummy", callback_userdata, message)
    init_mock.assert_called_once_with(
        mac_address=expected_mac_address, retry_count=retry_count, password=None
    )
    execute_command_mock.assert_called_once_with(
        mqtt_client="client_dummy",
        mqtt_message_payload=payload,
        update_device_info=fetch_device_info,
        mqtt_topic_prefix=topic_prefix,
    )
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors.base",
            logging.DEBUG,
            f"received topic={topic.decode()} payload={payload!r}",
        )
    ]


@pytest.mark.parametrize(
    ("mac_address", "expected_password"),
    [
        ("11:22:33:44:55:66", None),
        ("aa:bb:cc:dd:ee:ff", "secret"),
        ("11:22:33:dd:ee:ff", "äöü"),
    ],
)
def test__mqtt_command_callback_password(
    mac_address: str, expected_password: typing.Optional[str]
) -> None:
    ActorMock = _mock_actor_class(
        command_topic_levels=("switchbot", _MQTTTopicPlaceholder.MAC_ADDRESS)
    )
    message = MQTTMessage(topic=b"prefix-switchbot/" + mac_address.encode())
    message.payload = b"whatever"
    callback_userdata = _MQTTCallbackUserdata(
        retry_count=3,
        device_passwords={
            "11:22:33:44:55:77": "test",
            "aa:bb:cc:dd:ee:ff": "secret",
            "11:22:33:dd:ee:ff": "äöü",
        },
        fetch_device_info=True,
        mqtt_topic_prefix="prefix-",
    )
    with unittest.mock.patch.object(
        ActorMock, "__init__", return_value=None
    ) as init_mock, unittest.mock.patch.object(
        ActorMock, "execute_command"
    ) as execute_command_mock:
        ActorMock._mqtt_command_callback("client_dummy", callback_userdata, message)
    init_mock.assert_called_once_with(
        mac_address=mac_address, retry_count=3, password=expected_password
    )
    execute_command_mock.assert_called_once_with(
        mqtt_client="client_dummy",
        mqtt_message_payload=b"whatever",
        update_device_info=True,
        mqtt_topic_prefix="prefix-",
    )


@pytest.mark.parametrize(
    ("topic", "payload"),
    [
        (b"homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff", b"on"),
        (b"homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/change", b"ON"),
        (b"homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set/suffix", b"ON"),
    ],
)
def test__mqtt_command_callback_unexpected_topic(
    caplog: _pytest.logging.LogCaptureFixture, topic: bytes, payload: bytes
) -> None:
    ActorMock = _mock_actor_class(
        command_topic_levels=_ButtonAutomator.MQTT_COMMAND_TOPIC_LEVELS
    )
    message = MQTTMessage(topic=topic)
    message.payload = payload
    with unittest.mock.patch.object(
        ActorMock, "__init__", return_value=None
    ) as init_mock, unittest.mock.patch.object(
        ActorMock, "execute_command"
    ) as execute_command_mock, caplog.at_level(
        logging.DEBUG
    ):
        ActorMock._mqtt_command_callback(
            "client_dummy",
            _MQTTCallbackUserdata(
                retry_count=3,
                device_passwords={},
                fetch_device_info=True,
                mqtt_topic_prefix="homeassistant/",
            ),
            message,
        )
    init_mock.assert_not_called()
    execute_command_mock.assert_not_called()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors.base",
            logging.DEBUG,
            f"received topic={topic.decode()} payload={payload!r}",
        ),
        (
            "switchbot_mqtt._actors.base",
            logging.WARNING,
            f"unexpected topic {topic.decode()}",
        ),
    ]


@pytest.mark.parametrize(("mac_address", "payload"), [("aa:01:23:4E:RR:OR", b"ON")])
def test__mqtt_command_callback_invalid_mac_address(
    caplog: _pytest.logging.LogCaptureFixture, mac_address: str, payload: bytes
) -> None:
    ActorMock = _mock_actor_class(
        command_topic_levels=_ButtonAutomator.MQTT_COMMAND_TOPIC_LEVELS
    )
    topic = f"mqttprefix-switch/switchbot/{mac_address}/set".encode()
    message = MQTTMessage(topic=topic)
    message.payload = payload
    with unittest.mock.patch.object(
        ActorMock, "__init__", return_value=None
    ) as init_mock, unittest.mock.patch.object(
        ActorMock, "execute_command"
    ) as execute_command_mock, caplog.at_level(
        logging.DEBUG
    ):
        ActorMock._mqtt_command_callback(
            "client_dummy",
            _MQTTCallbackUserdata(
                retry_count=3,
                device_passwords={},
                fetch_device_info=True,
                mqtt_topic_prefix="mqttprefix-",
            ),
            message,
        )
    init_mock.assert_not_called()
    execute_command_mock.assert_not_called()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors.base",
            logging.DEBUG,
            f"received topic={topic.decode()} payload={payload!r}",
        ),
        (
            "switchbot_mqtt._actors.base",
            logging.WARNING,
            f"invalid mac address {mac_address}",
        ),
    ]


@pytest.mark.parametrize(
    ("topic", "payload"),
    [(b"homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set", b"ON")],
)
def test__mqtt_command_callback_ignore_retained(
    caplog: _pytest.logging.LogCaptureFixture, topic: bytes, payload: bytes
) -> None:
    ActorMock = _mock_actor_class(
        command_topic_levels=_ButtonAutomator.MQTT_COMMAND_TOPIC_LEVELS
    )
    message = MQTTMessage(topic=topic)
    message.payload = payload
    message.retain = True
    with unittest.mock.patch.object(
        ActorMock, "__init__", return_value=None
    ) as init_mock, unittest.mock.patch.object(
        ActorMock, "execute_command"
    ) as execute_command_mock, caplog.at_level(
        logging.DEBUG
    ):
        ActorMock._mqtt_command_callback(
            "client_dummy",
            _MQTTCallbackUserdata(
                retry_count=4,
                device_passwords={},
                fetch_device_info=True,
                mqtt_topic_prefix="homeassistant/",
            ),
            message,
        )
    init_mock.assert_not_called()
    execute_command_mock.assert_not_called()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors.base",
            logging.DEBUG,
            f"received topic={topic.decode()} payload={payload!r}",
        ),
        ("switchbot_mqtt._actors.base", logging.INFO, "ignoring retained message"),
    ]


@pytest.mark.parametrize(
    ("topic_prefix", "state_topic_levels", "mac_address", "expected_topic"),
    # https://www.home-assistant.io/docs/mqtt/discovery/#switches
    [
        (
            "homeassistant/",
            _ButtonAutomator.MQTT_STATE_TOPIC_LEVELS,
            "aa:bb:cc:dd:ee:ff",
            "homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/state",
        ),
        (
            "",
            ["switchbot", _MQTTTopicPlaceholder.MAC_ADDRESS, "state"],
            "aa:bb:cc:dd:ee:gg",
            "switchbot/aa:bb:cc:dd:ee:gg/state",
        ),
    ],
)
@pytest.mark.parametrize("state", [b"ON", b"CLOSE"])
@pytest.mark.parametrize("return_code", [MQTT_ERR_SUCCESS, MQTT_ERR_QUEUE_SIZE])
def test__report_state(
    caplog: _pytest.logging.LogCaptureFixture,
    topic_prefix: str,
    state_topic_levels: typing.Tuple[_MQTTTopicLevel, ...],
    mac_address: str,
    expected_topic: str,
    state: bytes,
    return_code: int,
) -> None:
    # pylint: disable=too-many-arguments
    class _ActorMock(_MQTTControlledActor):
        MQTT_STATE_TOPIC_LEVELS = state_topic_levels

        def __init__(
            self, mac_address: str, retry_count: int, password: typing.Optional[str]
        ) -> None:
            super().__init__(
                mac_address=mac_address, retry_count=retry_count, password=password
            )

        def execute_command(
            self,
            *,
            mqtt_message_payload: bytes,
            mqtt_client: Client,
            update_device_info: bool,
            mqtt_topic_prefix: str,
        ) -> None:
            pass

        def _get_device(self) -> None:
            return None

    mqtt_client_mock = unittest.mock.MagicMock()
    mqtt_client_mock.publish.return_value.rc = return_code
    with caplog.at_level(logging.DEBUG):
        actor = _ActorMock(mac_address=mac_address, retry_count=3, password=None)
        actor.report_state(
            state=state,
            mqtt_client=mqtt_client_mock,
            mqtt_topic_prefix=topic_prefix,
        )
    mqtt_client_mock.publish.assert_called_once_with(
        topic=expected_topic, payload=state, retain=True
    )
    assert caplog.record_tuples[0] == (
        "switchbot_mqtt._actors.base",
        logging.DEBUG,
        f"publishing topic={expected_topic} payload={state!r}",
    )
    if return_code == MQTT_ERR_SUCCESS:
        assert not caplog.records[1:]
    else:
        assert caplog.record_tuples[1:] == [
            (
                "switchbot_mqtt._actors.base",
                logging.ERROR,
                f"Failed to publish MQTT message on topic {expected_topic} (rc={return_code})",
            )
        ]
