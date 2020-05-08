import unittest.mock

import pytest

import switchbot_mqtt


@pytest.mark.parametrize(
    (
        "argv",
        "expected_mqtt_host",
        "expected_mqtt_port",
        "expected_username",
        "expected_password",
    ),
    [
        (
            ["", "--mqtt-host", "mqtt-broker.local"],
            "mqtt-broker.local",
            1883,
            None,
            None,
        ),
        (
            ["", "--mqtt-host", "mqtt-broker.local", "--mqtt-port", "8883"],
            "mqtt-broker.local",
            8883,
            None,
            None,
        ),
        (
            ["", "--mqtt-host", "mqtt-broker.local", "--mqtt-username", "me"],
            "mqtt-broker.local",
            1883,
            "me",
            None,
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
            ],
            "mqtt-broker.local",
            1883,
            "me",
            "secret",
        ),
    ],
)
def test__main(
    argv, expected_mqtt_host, expected_mqtt_port, expected_username, expected_password
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
    )
