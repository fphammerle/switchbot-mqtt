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
import socket
import ssl
import typing
import unittest.mock

import _pytest.logging  # pylint: disable=import-private-name; typing
import pytest
import aiomqtt
from paho.mqtt.client import MQTT_ERR_NO_CONN

# pylint: disable=import-private-name; internal
import switchbot_mqtt
import switchbot_mqtt._actors
from switchbot_mqtt._actors import _ButtonAutomator, _CurtainMotor
from switchbot_mqtt._actors.base import _MQTTControlledActor
from switchbot_mqtt._utils import _MQTTTopicLevel, _MQTTTopicPlaceholder

# pylint: disable=protected-access
# pylint: disable=too-many-arguments; these are tests, no API


@pytest.mark.asyncio
async def test__listen(caplog: _pytest.logging.LogCaptureFixture) -> None:
    mqtt_client = unittest.mock.AsyncMock()
    messages_mock = unittest.mock.AsyncMock()

    async def _msg_iter() -> typing.AsyncIterator[aiomqtt.Message]:
        for topic, payload in [
            ("/foo", b"foo1"),
            ("/baz/21/bar", b"42/2"),
            ("/baz/bar", b"nope"),
            ("/foo", b"foo2"),
        ]:
            yield aiomqtt.Message(
                topic=topic,
                payload=payload,
                qos=0,
                retain=False,
                mid=0,
                properties=None,
            )

    messages_mock.__aenter__.return_value.__aiter__.side_effect = _msg_iter
    mqtt_client.messages = lambda: messages_mock
    callback_foo = unittest.mock.AsyncMock()
    callback_bar = unittest.mock.AsyncMock()
    with caplog.at_level(logging.DEBUG):
        await switchbot_mqtt._listen(
            mqtt_client=mqtt_client,
            topic_callbacks=(("/foo", callback_foo), ("/baz/+/bar", callback_bar)),
            mqtt_topic_prefix="whatever/",
            retry_count=3,
            device_passwords={},
            fetch_device_info=False,
        )
    mqtt_client.publish.assert_awaited_once_with(
        topic="whatever/switchbot-mqtt/status", payload="online", retain=True
    )
    messages_mock.__aenter__.assert_awaited_once_with()
    assert callback_foo.await_count == 2
    assert not callback_foo.await_args_list[0].args
    kwargs = callback_foo.await_args_list[0].kwargs
    assert kwargs["message"].topic.value == "/foo"
    assert kwargs["message"].payload == b"foo1"
    del kwargs["message"]  # type: ignore
    assert kwargs == {
        "mqtt_client": mqtt_client,
        "mqtt_topic_prefix": "whatever/",
        "retry_count": 3,
        "device_passwords": {},
        "fetch_device_info": False,
    }
    assert callback_foo.await_args_list[1].kwargs["message"].payload == b"foo2"
    assert callback_bar.await_count == 1
    assert (
        callback_bar.await_args_list[0].kwargs["message"].topic.value == "/baz/21/bar"
    )
    assert callback_bar.await_args_list[0].kwargs["message"].payload == b"42/2"


@pytest.mark.parametrize(
    ("socket_family", "peername", "peername_log"),
    [
        (socket.AF_INET, ("mqtt-broker.local", 1883), "mqtt-broker.local:1883"),
        # https://github.com/fphammerle/switchbot-mqtt/issues/42#issuecomment-1173909335
        (socket.AF_INET6, ("::1", 1883, 0, 0), "[::1]:1883"),
    ],
)
def test__log_mqtt_connected(
    caplog: _pytest.logging.LogCaptureFixture,
    socket_family: int,  # socket.AddressFamily,
    peername: typing.Tuple[typing.Union[str, int]],
    peername_log: str,
) -> None:
    mqtt_client = unittest.mock.MagicMock()
    mqtt_client._client.socket().family = socket_family
    mqtt_client._client.socket().getpeername.return_value = peername
    with caplog.at_level(logging.INFO):
        switchbot_mqtt._log_mqtt_connected(mqtt_client)
    assert not caplog.records
    with caplog.at_level(logging.DEBUG):
        switchbot_mqtt._log_mqtt_connected(mqtt_client)
    assert caplog.record_tuples[0] == (
        "switchbot_mqtt",
        logging.DEBUG,
        f"connected to MQTT broker {peername_log}",
    )


@pytest.mark.asyncio()
@pytest.mark.parametrize("mqtt_host", ["mqtt-broker.local"])
@pytest.mark.parametrize("mqtt_port", [1234])
@pytest.mark.parametrize("retry_count", [3, 21])
@pytest.mark.parametrize(
    "device_passwords",
    [{}, {"11:22:33:44:55:66": "password", "aa:bb:cc:dd:ee:ff": "secret"}],
)
@pytest.mark.parametrize("fetch_device_info", [True, False])
async def test__run(
    caplog: _pytest.logging.LogCaptureFixture,
    mqtt_host: str,
    mqtt_port: int,
    retry_count: int,
    device_passwords: typing.Dict[str, str],
    fetch_device_info: bool,
) -> None:
    with unittest.mock.patch("aiomqtt.Client") as mqtt_client_mock, unittest.mock.patch(
        "switchbot_mqtt._log_mqtt_connected"
    ) as log_connected_mock, unittest.mock.patch(
        "switchbot_mqtt._listen"
    ) as listen_mock, caplog.at_level(
        logging.DEBUG
    ):
        await switchbot_mqtt._run(
            mqtt_host=mqtt_host,
            mqtt_port=mqtt_port,
            mqtt_disable_tls=False,
            mqtt_username=None,
            mqtt_password=None,
            mqtt_topic_prefix="home/",
            retry_count=retry_count,
            device_passwords=device_passwords,
            fetch_device_info=fetch_device_info,
        )
    mqtt_client_mock.assert_called_once()
    assert not mqtt_client_mock.call_args.args
    init_kwargs = mqtt_client_mock.call_args.kwargs
    assert isinstance(init_kwargs.pop("tls_context"), ssl.SSLContext)
    assert init_kwargs.pop("will") == aiomqtt.Will(
        topic="home/switchbot-mqtt/status",
        payload="offline",
        qos=0,
        retain=True,
        properties=None,
    )
    assert init_kwargs == {
        "hostname": mqtt_host,
        "port": mqtt_port,
        "username": None,
        "password": None,
    }
    log_connected_mock.assert_called_once()
    subscribe_mock = mqtt_client_mock().__aenter__.return_value.subscribe
    assert subscribe_mock.await_count == (5 if fetch_device_info else 3)
    subscribe_mock.assert_has_awaits(
        (
            unittest.mock.call(topic)
            for topic in [
                "home/switch/switchbot/+/set",
                "home/cover/switchbot-curtain/+/set",
                "home/cover/switchbot-curtain/+/position/set-percent",
            ]
        ),
        any_order=True,
    )
    if fetch_device_info:
        subscribe_mock.assert_has_awaits(
            (
                unittest.mock.call("home/switch/switchbot/+/request-device-info"),
                unittest.mock.call(
                    "home/cover/switchbot-curtain/+/request-device-info"
                ),
            ),
            any_order=True,
        )
    listen_mock.assert_awaited_once()
    assert listen_mock.await_args is not None  # for mypy
    assert not listen_mock.await_args.args
    listen_kwargs = listen_mock.await_args.kwargs
    assert (
        listen_kwargs.pop("mqtt_client")  # type: ignore
        == mqtt_client_mock().__aenter__.return_value
    )
    topic_callbacks = listen_kwargs.pop("topic_callbacks")  # type: ignore
    assert len(topic_callbacks) == (5 if fetch_device_info else 3)
    assert (
        "home/switch/switchbot/+/set",
        switchbot_mqtt._actors._ButtonAutomator._mqtt_command_callback,
    ) in topic_callbacks
    assert (
        "home/cover/switchbot-curtain/+/set",
        switchbot_mqtt._actors._CurtainMotor._mqtt_command_callback,
    ) in topic_callbacks
    assert (
        "home/cover/switchbot-curtain/+/position/set-percent",
        switchbot_mqtt._actors._CurtainMotor._mqtt_set_position_callback,
    ) in topic_callbacks
    if fetch_device_info:
        assert (
            "home/switch/switchbot/+/request-device-info",
            switchbot_mqtt._actors._ButtonAutomator._mqtt_update_device_info_callback,
        ) in topic_callbacks
        assert (
            "home/cover/switchbot-curtain/+/request-device-info",
            switchbot_mqtt._actors._CurtainMotor._mqtt_update_device_info_callback,
        ) in topic_callbacks
    assert listen_kwargs == {
        "device_passwords": device_passwords,
        "fetch_device_info": fetch_device_info,
        "mqtt_topic_prefix": "home/",
        "retry_count": retry_count,
    }
    assert caplog.record_tuples[0] == (
        "switchbot_mqtt",
        logging.INFO,
        f"connecting to MQTT broker {mqtt_host}:{mqtt_port} (TLS enabled)",
    )
    assert len(caplog.record_tuples) == (5 if fetch_device_info else 3) + 1
    assert (
        "switchbot_mqtt._actors.base",
        logging.INFO,
        "subscribing to MQTT topic 'home/switch/switchbot/+/set'",
    ) in caplog.record_tuples
    assert (
        "switchbot_mqtt._actors.base",
        logging.INFO,
        "subscribing to MQTT topic 'home/cover/switchbot-curtain/+/set'",
    ) in caplog.record_tuples


@pytest.mark.asyncio
@pytest.mark.parametrize("mqtt_disable_tls", [True, False])
async def test__run_tls(
    caplog: _pytest.logging.LogCaptureFixture, mqtt_disable_tls: bool
) -> None:
    with unittest.mock.patch("aiomqtt.Client") as mqtt_client_mock, unittest.mock.patch(
        "switchbot_mqtt._listen"
    ), caplog.at_level(logging.INFO):
        await switchbot_mqtt._run(
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
    mqtt_client_mock.assert_called_once()
    assert not mqtt_client_mock.call_args.args
    kwargs = mqtt_client_mock.call_args.kwargs
    if mqtt_disable_tls:
        assert kwargs["tls_context"] is None
        assert caplog.record_tuples[0][2].endswith(" (TLS disabled)")
    else:
        assert isinstance(kwargs["tls_context"], ssl.SSLContext)
        assert caplog.record_tuples[0][2].endswith(" (TLS enabled)")


@pytest.mark.asyncio
@pytest.mark.parametrize("mqtt_host", ["mqtt-broker.local"])
@pytest.mark.parametrize("mqtt_port", [1833])
@pytest.mark.parametrize("mqtt_username", ["me"])
@pytest.mark.parametrize("mqtt_password", [None, "secret"])
async def test__run_authentication(
    mqtt_host: str,
    mqtt_port: int,
    mqtt_username: str,
    mqtt_password: typing.Optional[str],
) -> None:
    with unittest.mock.patch("aiomqtt.Client") as mqtt_client_mock, unittest.mock.patch(
        "switchbot_mqtt._listen"
    ):
        await switchbot_mqtt._run(
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
    mqtt_client_mock.assert_called_once()
    assert not mqtt_client_mock.call_args.args
    kwargs = mqtt_client_mock.call_args.kwargs
    assert kwargs["username"] == mqtt_username
    assert kwargs["password"] == mqtt_password


@pytest.mark.asyncio
@pytest.mark.parametrize("mqtt_host", ["mqtt-broker.local"])
@pytest.mark.parametrize("mqtt_port", [1833])
@pytest.mark.parametrize("mqtt_password", ["secret"])
async def test__run_authentication_missing_username(
    mqtt_host: str, mqtt_port: int, mqtt_password: str
) -> None:
    with pytest.raises(ValueError, match=r"^Missing MQTT username$"):
        await switchbot_mqtt._run(
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

        async def execute_command(
            self,
            *,
            mqtt_message_payload: bytes,
            mqtt_client: aiomqtt.Client,
            update_device_info: bool,
            mqtt_topic_prefix: str,
        ) -> None:
            pass

        def _get_device(self) -> None:
            return None

    return _ActorMock


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("topic_levels", "topic", "expected_mac_address"),
    [
        (
            switchbot_mqtt._actors._ButtonAutomator._MQTT_UPDATE_DEVICE_INFO_TOPIC_LEVELS,
            "prfx/switch/switchbot/aa:bb:cc:dd:ee:ff/request-device-info",
            "aa:bb:cc:dd:ee:ff",
        ),
    ],
)
@pytest.mark.parametrize("payload", [b"", b"whatever"])
async def test__mqtt_update_device_info_callback(
    caplog: _pytest.logging.LogCaptureFixture,
    topic_levels: typing.Tuple[_MQTTTopicLevel, ...],
    topic: str,
    expected_mac_address: str,
    payload: bytes,
) -> None:
    ActorMock = _mock_actor_class(request_info_levels=topic_levels)
    message = aiomqtt.Message(
        topic=topic, payload=payload, qos=0, retain=False, mid=0, properties=None
    )
    with unittest.mock.patch.object(
        ActorMock, "__init__", return_value=None
    ) as init_mock, unittest.mock.patch.object(
        ActorMock, "_update_and_report_device_info"
    ) as update_mock, caplog.at_level(
        logging.DEBUG
    ):
        await ActorMock._mqtt_update_device_info_callback(
            mqtt_client="client_dummy",
            message=message,
            mqtt_topic_prefix="prfx/",
            retry_count=21,  # tested in test__mqtt_command_callback
            device_passwords={},
            fetch_device_info=True,
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
            f"received topic={topic} payload={payload!r}",
        )
    ]


@pytest.mark.asyncio
async def test__mqtt_update_device_info_callback_ignore_retained(
    caplog: _pytest.logging.LogCaptureFixture,
) -> None:
    ActorMock = _mock_actor_class(
        request_info_levels=(_MQTTTopicPlaceholder.MAC_ADDRESS, "request")
    )
    message = aiomqtt.Message(
        topic="aa:bb:cc:dd:ee:ff/request",
        payload=b"",
        qos=0,
        retain=True,
        mid=0,
        properties=None,
    )
    with unittest.mock.patch.object(
        ActorMock, "__init__", return_value=None
    ) as init_mock, unittest.mock.patch.object(
        ActorMock, "execute_command"
    ) as execute_command_mock, caplog.at_level(
        logging.DEBUG
    ):
        await ActorMock._mqtt_update_device_info_callback(
            mqtt_client="client_dummy",
            message=message,
            mqtt_topic_prefix="ignored",
            retry_count=21,
            device_passwords={},
            fetch_device_info=True,
        )
    init_mock.assert_not_called()
    execute_command_mock.assert_not_called()
    execute_command_mock.assert_not_awaited()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors.base",
            logging.DEBUG,
            "received topic=aa:bb:cc:dd:ee:ff/request payload=b''",
        ),
        ("switchbot_mqtt._actors.base", logging.INFO, "ignoring retained message"),
    ]


@pytest.mark.asyncio
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
            "homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set",
            b"ON",
            "aa:bb:cc:dd:ee:ff",
        ),
        (
            "homeassistant/",
            _ButtonAutomator.MQTT_COMMAND_TOPIC_LEVELS,
            "homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set",
            b"OFF",
            "aa:bb:cc:dd:ee:ff",
        ),
        (
            "homeassistant/",
            _ButtonAutomator.MQTT_COMMAND_TOPIC_LEVELS,
            "homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set",
            b"on",
            "aa:bb:cc:dd:ee:ff",
        ),
        (
            "homeassistant/",
            _ButtonAutomator.MQTT_COMMAND_TOPIC_LEVELS,
            "homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set",
            b"off",
            "aa:bb:cc:dd:ee:ff",
        ),
        (
            "prefix-",
            _ButtonAutomator.MQTT_COMMAND_TOPIC_LEVELS,
            "prefix-switch/switchbot/aa:01:23:45:67:89/set",
            b"ON",
            "aa:01:23:45:67:89",
        ),
        (
            "",
            ["switchbot", _MQTTTopicPlaceholder.MAC_ADDRESS],
            "switchbot/aa:01:23:45:67:89",
            b"ON",
            "aa:01:23:45:67:89",
        ),
        (
            "homeassistant/",
            _CurtainMotor.MQTT_COMMAND_TOPIC_LEVELS,
            "homeassistant/cover/switchbot-curtain/aa:01:23:45:67:89/set",
            b"OPEN",
            "aa:01:23:45:67:89",
        ),
    ],
)
@pytest.mark.parametrize("retry_count", (3, 42))
@pytest.mark.parametrize("fetch_device_info", [True, False])
async def test__mqtt_command_callback(
    caplog: _pytest.logging.LogCaptureFixture,
    topic_prefix: str,
    command_topic_levels: typing.Tuple[_MQTTTopicLevel, ...],
    topic: str,
    payload: bytes,
    expected_mac_address: str,
    retry_count: int,
    fetch_device_info: bool,
) -> None:
    ActorMock = _mock_actor_class(command_topic_levels=command_topic_levels)
    message = aiomqtt.Message(
        topic=topic, payload=payload, qos=0, retain=False, mid=0, properties=None
    )
    with unittest.mock.patch.object(
        ActorMock, "__init__", return_value=None
    ) as init_mock, unittest.mock.patch.object(
        ActorMock, "execute_command"
    ) as execute_command_mock, caplog.at_level(
        logging.DEBUG
    ):
        await ActorMock._mqtt_command_callback(
            mqtt_client="client_dummy",
            message=message,
            retry_count=retry_count,
            device_passwords={},
            fetch_device_info=fetch_device_info,
            mqtt_topic_prefix=topic_prefix,
        )
    init_mock.assert_called_once_with(
        mac_address=expected_mac_address, retry_count=retry_count, password=None
    )
    execute_command_mock.assert_awaited_once_with(
        mqtt_client="client_dummy",
        mqtt_message_payload=payload,
        update_device_info=fetch_device_info,
        mqtt_topic_prefix=topic_prefix,
    )
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors.base",
            logging.DEBUG,
            f"received topic={topic} payload={payload!r}",
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mac_address", "expected_password"),
    [
        ("11:22:33:44:55:66", None),
        ("aa:bb:cc:dd:ee:ff", "secret"),
        ("11:22:33:dd:ee:ff", "äöü"),
    ],
)
async def test__mqtt_command_callback_password(
    mac_address: str, expected_password: typing.Optional[str]
) -> None:
    ActorMock = _mock_actor_class(
        command_topic_levels=("switchbot", _MQTTTopicPlaceholder.MAC_ADDRESS)
    )
    message = aiomqtt.Message(
        topic="prefix-switchbot/" + mac_address,
        payload=b"whatever",
        qos=0,
        retain=False,
        mid=0,
        properties=None,
    )
    with unittest.mock.patch.object(
        ActorMock, "__init__", return_value=None
    ) as init_mock, unittest.mock.patch.object(
        ActorMock, "execute_command"
    ) as execute_command_mock:
        await ActorMock._mqtt_command_callback(
            mqtt_client="client_dummy",
            message=message,
            retry_count=3,
            device_passwords={
                "11:22:33:44:55:77": "test",
                "aa:bb:cc:dd:ee:ff": "secret",
                "11:22:33:dd:ee:ff": "äöü",
            },
            fetch_device_info=True,
            mqtt_topic_prefix="prefix-",
        )
    init_mock.assert_called_once_with(
        mac_address=mac_address, retry_count=3, password=expected_password
    )
    execute_command_mock.assert_awaited_once_with(
        mqtt_client="client_dummy",
        mqtt_message_payload=b"whatever",
        update_device_info=True,
        mqtt_topic_prefix="prefix-",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("topic", "payload"),
    [
        ("homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff", b"on"),
        ("homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/change", b"ON"),
        ("homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set/suffix", b"ON"),
    ],
)
async def test__mqtt_command_callback_unexpected_topic(
    caplog: _pytest.logging.LogCaptureFixture, topic: str, payload: bytes
) -> None:
    ActorMock = _mock_actor_class(
        command_topic_levels=_ButtonAutomator.MQTT_COMMAND_TOPIC_LEVELS
    )
    message = aiomqtt.Message(
        topic=topic, payload=payload, qos=0, retain=False, mid=0, properties=None
    )
    with unittest.mock.patch.object(
        ActorMock, "__init__", return_value=None
    ) as init_mock, unittest.mock.patch.object(
        ActorMock, "execute_command"
    ) as execute_command_mock, caplog.at_level(
        logging.DEBUG
    ):
        await ActorMock._mqtt_command_callback(
            mqtt_client="client_dummy",
            message=message,
            retry_count=3,
            device_passwords={},
            fetch_device_info=True,
            mqtt_topic_prefix="homeassistant/",
        )
    init_mock.assert_not_called()
    execute_command_mock.assert_not_called()
    execute_command_mock.assert_not_awaited()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors.base",
            logging.DEBUG,
            f"received topic={topic} payload={payload!r}",
        ),
        (
            "switchbot_mqtt._actors.base",
            logging.WARNING,
            f"unexpected topic {topic}",
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(("mac_address", "payload"), [("aa:01:23:4E:RR:OR", b"ON")])
async def test__mqtt_command_callback_invalid_mac_address(
    caplog: _pytest.logging.LogCaptureFixture, mac_address: str, payload: bytes
) -> None:
    ActorMock = _mock_actor_class(
        command_topic_levels=_ButtonAutomator.MQTT_COMMAND_TOPIC_LEVELS
    )
    topic = f"mqttprefix-switch/switchbot/{mac_address}/set"
    message = aiomqtt.Message(
        topic=topic, payload=payload, qos=0, retain=False, mid=0, properties=None
    )
    with unittest.mock.patch.object(
        ActorMock, "__init__", return_value=None
    ) as init_mock, unittest.mock.patch.object(
        ActorMock, "execute_command"
    ) as execute_command_mock, caplog.at_level(
        logging.DEBUG
    ):
        await ActorMock._mqtt_command_callback(
            mqtt_client="client_dummy",
            message=message,
            retry_count=3,
            device_passwords={},
            fetch_device_info=True,
            mqtt_topic_prefix="mqttprefix-",
        )
    init_mock.assert_not_called()
    execute_command_mock.assert_not_called()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors.base",
            logging.DEBUG,
            f"received topic={topic} payload={payload!r}",
        ),
        (
            "switchbot_mqtt._actors.base",
            logging.WARNING,
            f"invalid mac address {mac_address}",
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("topic", "payload"),
    [("homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set", b"ON")],
)
async def test__mqtt_command_callback_ignore_retained(
    caplog: _pytest.logging.LogCaptureFixture, topic: str, payload: bytes
) -> None:
    ActorMock = _mock_actor_class(
        command_topic_levels=_ButtonAutomator.MQTT_COMMAND_TOPIC_LEVELS
    )
    message = aiomqtt.Message(
        topic=topic, payload=payload, qos=0, retain=True, mid=0, properties=None
    )
    with unittest.mock.patch.object(
        ActorMock, "__init__", return_value=None
    ) as init_mock, unittest.mock.patch.object(
        ActorMock, "execute_command"
    ) as execute_command_mock, caplog.at_level(
        logging.DEBUG
    ):
        await ActorMock._mqtt_command_callback(
            mqtt_client="client_dummy",
            message=message,
            retry_count=4,
            device_passwords={},
            fetch_device_info=True,
            mqtt_topic_prefix="homeassistant/",
        )
    init_mock.assert_not_called()
    execute_command_mock.assert_not_called()
    execute_command_mock.assert_not_awaited()
    assert caplog.record_tuples == [
        (
            "switchbot_mqtt._actors.base",
            logging.DEBUG,
            f"received topic={topic} payload={payload!r}",
        ),
        ("switchbot_mqtt._actors.base", logging.INFO, "ignoring retained message"),
    ]


@pytest.mark.asyncio
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
@pytest.mark.parametrize("mqtt_publish_fails", [False, True])
async def test__report_state(
    caplog: _pytest.logging.LogCaptureFixture,
    topic_prefix: str,
    state_topic_levels: typing.Tuple[_MQTTTopicLevel, ...],
    mac_address: str,
    expected_topic: str,
    state: bytes,
    mqtt_publish_fails: bool,
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

        async def execute_command(
            self,
            *,
            mqtt_message_payload: bytes,
            mqtt_client: aiomqtt.Client,
            update_device_info: bool,
            mqtt_topic_prefix: str,
        ) -> None:
            pass

        def _get_device(self) -> None:
            return None

    mqtt_client_mock = unittest.mock.AsyncMock()
    if mqtt_publish_fails:
        # https://github.com/sbtinstruments/aiomqtt/blob/v1.2.1/aiomqtt/client.py#L678
        mqtt_client_mock.publish.side_effect = aiomqtt.MqttCodeError(
            MQTT_ERR_NO_CONN, "Could not publish message"
        )
    with caplog.at_level(logging.DEBUG):
        actor = _ActorMock(mac_address=mac_address, retry_count=3, password=None)
        await actor.report_state(
            state=state, mqtt_client=mqtt_client_mock, mqtt_topic_prefix=topic_prefix
        )
    mqtt_client_mock.publish.assert_awaited_once_with(
        topic=expected_topic, payload=state, retain=True
    )
    assert caplog.record_tuples[0] == (
        "switchbot_mqtt._actors.base",
        logging.DEBUG,
        f"publishing topic={expected_topic} payload={state!r}",
    )
    if not mqtt_publish_fails:
        assert not caplog.records[1:]
    else:
        assert caplog.record_tuples[1:] == [
            (
                "switchbot_mqtt._actors.base",
                logging.ERROR,
                f"Failed to publish MQTT message on topic {expected_topic}:"
                " aiomqtt.MqttCodeError [code:4] The client is not currently connected.",
            )
        ]
