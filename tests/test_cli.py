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

import json
import logging
import pathlib
import subprocess
import typing
import unittest.mock

import _pytest.capture
import pytest

import switchbot_mqtt
import switchbot_mqtt._cli

# pylint: disable=protected-access; tests
# pylint: disable=too-many-arguments; these are tests, no API


def test_console_entry_point() -> None:
    assert subprocess.run(
        ["switchbot-mqtt", "--help"], stdout=subprocess.PIPE, check=True
    ).stdout.startswith(b"usage: ")


@pytest.mark.parametrize(
    (
        "argv",
        "expected_mqtt_host",
        "expected_mqtt_port",
        "expected_username",
        "expected_password",
        "expected_retry_count",
    ),
    [
        (
            ["", "--mqtt-host", "mqtt-broker.local"],
            "mqtt-broker.local",
            1883,
            None,
            None,
            3,
        ),
        (
            ["", "--mqtt-host", "mqtt-broker.local", "--mqtt-port", "8883"],
            "mqtt-broker.local",
            8883,
            None,
            None,
            3,
        ),
        (
            ["", "--mqtt-host", "mqtt-broker.local", "--mqtt-username", "me"],
            "mqtt-broker.local",
            1883,
            "me",
            None,
            3,
        ),
        (
            [
                "",
                "--mqtt-host",
                "mqtt-broker.local",
                "--mqtt-username",
                "me",
                "--mqtt-password",
                "secret",
                "--retries",
                "21",
            ],
            "mqtt-broker.local",
            1883,
            "me",
            "secret",
            21,
        ),
    ],
)
def test__main(
    argv: typing.List[str],
    expected_mqtt_host: str,
    expected_mqtt_port: int,
    expected_username: str,
    expected_password: str,
    expected_retry_count: int,
) -> None:
    with unittest.mock.patch("switchbot_mqtt._run") as run_mock, unittest.mock.patch(
        "sys.argv", argv
    ), pytest.warns(UserWarning, match=r"Please add --mqtt-disable-tls\b"):
        switchbot_mqtt._cli._main()
    run_mock.assert_called_once_with(
        mqtt_host=expected_mqtt_host,
        mqtt_port=expected_mqtt_port,
        mqtt_disable_tls=True,
        mqtt_username=expected_username,
        mqtt_password=expected_password,
        mqtt_topic_prefix="homeassistant/",
        retry_count=expected_retry_count,
        device_passwords={},
        fetch_device_info=False,
    )


@pytest.mark.parametrize(
    ("mqtt_password_file_content", "expected_password"),
    [
        ("secret", "secret"),
        ("secret space", "secret space"),
        ("secret   ", "secret   "),
        ("  secret ", "  secret "),
        ("secret\n", "secret"),
        ("secret\n\n", "secret\n"),
        ("secret\r\n", "secret"),
        ("secret\n\r\n", "secret\n"),
        ("你好\n", "你好"),
    ],
)
def test__main_mqtt_password_file(
    tmp_path: pathlib.Path, mqtt_password_file_content: str, expected_password: str
) -> None:
    mqtt_password_path = tmp_path.joinpath("mqtt-password")
    mqtt_password_path.write_text(mqtt_password_file_content, encoding="utf8")
    with unittest.mock.patch("switchbot_mqtt._run") as run_mock, unittest.mock.patch(
        "sys.argv",
        [
            "",
            "--mqtt-host",
            "localhost",
            "--mqtt-username",
            "me",
            "--mqtt-password-file",
            str(mqtt_password_path),
        ],
    ):
        switchbot_mqtt._cli._main()
    run_mock.assert_called_once_with(
        mqtt_host="localhost",
        mqtt_port=1883,
        mqtt_disable_tls=True,
        mqtt_username="me",
        mqtt_password=expected_password,
        mqtt_topic_prefix="homeassistant/",
        retry_count=3,
        device_passwords={},
        fetch_device_info=False,
    )


def test__main_mqtt_password_file_collision(
    capsys: _pytest.capture.CaptureFixture,
) -> None:
    with unittest.mock.patch(
        "sys.argv",
        [
            "",
            "--mqtt-host",
            "localhost",
            "--mqtt-username",
            "me",
            "--mqtt-password",
            "secret",
            "--mqtt-password-file",
            "/var/lib/secrets/mqtt/password",
        ],
    ):
        with pytest.raises(SystemExit):
            switchbot_mqtt._cli._main()
    out, err = capsys.readouterr()
    assert not out
    assert (
        "argument --mqtt-password-file: not allowed with argument --mqtt-password\n"
        in err
    )


@pytest.mark.parametrize(
    "device_passwords",
    [
        {},
        {"11:22:33:44:55:66": "password", "aa:bb:cc:dd:ee:ff": "secret"},
    ],
)
def test__main_device_password_file(
    tmp_path: pathlib.Path, device_passwords: typing.Dict[str, str]
) -> None:
    device_passwords_path = tmp_path.joinpath("passwords.json")
    device_passwords_path.write_text(json.dumps(device_passwords), encoding="utf8")
    with unittest.mock.patch("switchbot_mqtt._run") as run_mock, unittest.mock.patch(
        "sys.argv",
        [
            "",
            "--mqtt-host",
            "localhost",
            "--device-password-file",
            str(device_passwords_path),
        ],
    ):
        switchbot_mqtt._cli._main()
    run_mock.assert_called_once_with(
        mqtt_host="localhost",
        mqtt_port=1883,
        mqtt_disable_tls=True,
        mqtt_username=None,
        mqtt_password=None,
        mqtt_topic_prefix="homeassistant/",
        retry_count=3,
        device_passwords=device_passwords,
        fetch_device_info=False,
    )


_RUN_DEFAULT_KWARGS: typing.Dict[str, typing.Any] = {
    "mqtt_host": "localhost",
    "mqtt_port": 1883,
    "mqtt_disable_tls": True,
    "mqtt_username": None,
    "mqtt_password": None,
    "mqtt_topic_prefix": "homeassistant/",
    "retry_count": 3,
    "device_passwords": {},
    "fetch_device_info": False,
}


def test__main_mqtt_disable_tls_implicit() -> None:
    with unittest.mock.patch("switchbot_mqtt._run") as run_mock, unittest.mock.patch(
        "sys.argv", ["", "--mqtt-host", "mqtt.local"]
    ), pytest.warns(UserWarning, match=r"Please add --mqtt-disable-tls\b"):
        switchbot_mqtt._cli._main()
    run_mock.assert_called_once_with(
        **{
            **_RUN_DEFAULT_KWARGS,
            "mqtt_host": "mqtt.local",
            "mqtt_disable_tls": True,
            "mqtt_port": 1883,
        }
    )


def test__main_mqtt_enable_tls() -> None:
    with unittest.mock.patch("switchbot_mqtt._run") as run_mock, unittest.mock.patch(
        "sys.argv", ["", "--mqtt-host", "mqtt.local", "--mqtt-enable-tls"]
    ):
        switchbot_mqtt._cli._main()
    run_mock.assert_called_once_with(
        **{
            **_RUN_DEFAULT_KWARGS,
            "mqtt_host": "mqtt.local",
            "mqtt_disable_tls": False,
            "mqtt_port": 8883,
        }
    )


def test__main_mqtt_enable_tls_overwrite_port() -> None:
    with unittest.mock.patch("switchbot_mqtt._run") as run_mock, unittest.mock.patch(
        "sys.argv",
        ["", "--mqtt-host", "mqtt.local", "--mqtt-port", "1883", "--mqtt-enable-tls"],
    ):
        switchbot_mqtt._cli._main()
    run_mock.assert_called_once_with(
        **{
            **_RUN_DEFAULT_KWARGS,
            "mqtt_host": "mqtt.local",
            "mqtt_disable_tls": False,
            "mqtt_port": 1883,
        }
    )


def test__main_mqtt_tls_collision(capsys: _pytest.capture.CaptureFixture) -> None:
    with unittest.mock.patch("switchbot_mqtt._run") as run_mock, unittest.mock.patch(
        "sys.argv",
        ["", "--mqtt-host", "mqtt.local", "--mqtt-enable-tls", "--mqtt-disable-tls"],
    ), pytest.raises(SystemExit):
        switchbot_mqtt._cli._main()
    run_mock.assert_not_called()
    assert (
        "error: argument --mqtt-disable-tls: not allowed with argument --mqtt-enable-tls\n"
        in capsys.readouterr()[1]
    )


@pytest.mark.parametrize(
    ("additional_argv", "expected_topic_prefix"),
    [([], "homeassistant/"), (["--mqtt-topic-prefix", ""], "")],
)
def test__main_mqtt_topic_prefix(
    additional_argv: typing.List[str], expected_topic_prefix: str
) -> None:
    with unittest.mock.patch("switchbot_mqtt._run") as run_mock, unittest.mock.patch(
        "sys.argv", ["", "--mqtt-host", "localhost"] + additional_argv
    ):
        switchbot_mqtt._cli._main()
    run_mock.assert_called_once_with(
        **{**_RUN_DEFAULT_KWARGS, "mqtt_topic_prefix": expected_topic_prefix}
    )


def test__main_fetch_device_info() -> None:
    with unittest.mock.patch("switchbot_mqtt._run") as run_mock, unittest.mock.patch(
        "sys.argv",
        [
            "",
            "--mqtt-host",
            "localhost",
        ],
    ):
        switchbot_mqtt._cli._main()
    run_mock.assert_called_once_with(
        **{**_RUN_DEFAULT_KWARGS, "fetch_device_info": False}
    )
    with unittest.mock.patch("switchbot_mqtt._run") as run_mock, unittest.mock.patch(
        "sys.argv",
        ["", "--mqtt-host", "localhost", "--fetch-device-info"],
    ):
        switchbot_mqtt._cli._main()
    run_mock.assert_called_once_with(
        **{**_RUN_DEFAULT_KWARGS, "fetch_device_info": True}
    )
    with unittest.mock.patch("switchbot_mqtt._run") as run_mock, unittest.mock.patch(
        "sys.argv",
        ["", "--mqtt-host", "localhost"],
    ), unittest.mock.patch.dict("os.environ", {"FETCH_DEVICE_INFO": "21"}):
        switchbot_mqtt._cli._main()
    run_mock.assert_called_once_with(
        **{**_RUN_DEFAULT_KWARGS, "fetch_device_info": True}
    )
    with unittest.mock.patch("switchbot_mqtt._run") as run_mock, unittest.mock.patch(
        "sys.argv",
        ["", "--mqtt-host", "localhost"],
    ), unittest.mock.patch.dict("os.environ", {"FETCH_DEVICE_INFO": ""}):
        switchbot_mqtt._cli._main()
    run_mock.assert_called_once_with(
        **{**_RUN_DEFAULT_KWARGS, "fetch_device_info": False}
    )
    with unittest.mock.patch("switchbot_mqtt._run") as run_mock, unittest.mock.patch(
        "sys.argv",
        ["", "--mqtt-host", "localhost"],
    ), unittest.mock.patch.dict("os.environ", {"FETCH_DEVICE_INFO": " "}):
        switchbot_mqtt._cli._main()
    run_mock.assert_called_once_with(
        **{**_RUN_DEFAULT_KWARGS, "fetch_device_info": True}
    )


@pytest.mark.parametrize(
    ("additional_argv", "root_log_level", "log_format"),
    [
        ([], logging.INFO, "%(message)s"),
        (
            ["--debug"],
            logging.DEBUG,
            "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s:%(message)s",
        ),
    ],
)
def test__main_log_config(
    additional_argv: typing.List[str], root_log_level: int, log_format: str
) -> None:
    with unittest.mock.patch(
        "sys.argv", ["", "--mqtt-host", "localhost"] + additional_argv
    ), unittest.mock.patch(
        "logging.basicConfig"
    ) as logging_basic_config_mock, unittest.mock.patch(
        "switchbot_mqtt._run"
    ):
        switchbot_mqtt._cli._main()
    logging_basic_config_mock.assert_called_once_with(
        level=root_log_level, format=log_format, datefmt="%Y-%m-%dT%H:%M:%S%z"
    )
