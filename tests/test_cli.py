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
import unittest.mock

import pytest

import switchbot_mqtt

# pylint: disable=too-many-arguments; these are tests, no API


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
    argv,
    expected_mqtt_host,
    expected_mqtt_port,
    expected_username,
    expected_password,
    expected_retry_count,
):
    with unittest.mock.patch("switchbot_mqtt._run") as run_mock, unittest.mock.patch(
        "sys.argv", argv
    ):
        # pylint: disable=protected-access
        switchbot_mqtt._main()
    run_mock.assert_called_once_with(
        mqtt_host=expected_mqtt_host,
        mqtt_port=expected_mqtt_port,
        mqtt_username=expected_username,
        mqtt_password=expected_password,
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
    tmpdir, mqtt_password_file_content, expected_password
):
    mqtt_password_path = tmpdir.join("mqtt-password")
    with mqtt_password_path.open("w") as mqtt_password_file:
        mqtt_password_file.write(mqtt_password_file_content)
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
        # pylint: disable=protected-access
        switchbot_mqtt._main()
    run_mock.assert_called_once_with(
        mqtt_host="localhost",
        mqtt_port=1883,
        mqtt_username="me",
        mqtt_password=expected_password,
        retry_count=3,
        device_passwords={},
        fetch_device_info=False,
    )


def test__main_mqtt_password_file_collision(capsys):
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
            # pylint: disable=protected-access
            switchbot_mqtt._main()
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
def test__main_device_password_file(tmpdir, device_passwords):
    device_passwords_path = tmpdir.join("passwords.json")
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
        # pylint: disable=protected-access
        switchbot_mqtt._main()
    run_mock.assert_called_once_with(
        mqtt_host="localhost",
        mqtt_port=1883,
        mqtt_username=None,
        mqtt_password=None,
        retry_count=3,
        device_passwords=device_passwords,
        fetch_device_info=False,
    )


def test__main_fetch_device_info():
    with unittest.mock.patch("switchbot_mqtt._run") as run_mock, unittest.mock.patch(
        "sys.argv",
        [
            "",
            "--mqtt-host",
            "localhost",
        ],
    ):
        # pylint: disable=protected-access
        switchbot_mqtt._main()
    default_kwargs = dict(
        mqtt_host="localhost",
        mqtt_port=1883,
        mqtt_username=None,
        mqtt_password=None,
        retry_count=3,
        device_passwords={},
    )
    run_mock.assert_called_once_with(fetch_device_info=False, **default_kwargs)
    with unittest.mock.patch("switchbot_mqtt._run") as run_mock, unittest.mock.patch(
        "sys.argv",
        ["", "--mqtt-host", "localhost", "--fetch-device-info"],
    ):
        # pylint: disable=protected-access
        switchbot_mqtt._main()
    run_mock.assert_called_once_with(fetch_device_info=True, **default_kwargs)
