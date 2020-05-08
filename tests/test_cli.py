import unittest.mock

import pytest

import switchbot_mqtt


@pytest.mark.parametrize(
    ("argv", "expected_mqtt_host", "expected_mqtt_port"),
    [
        (["", "--mqtt-host", "mqtt-broker.local"], "mqtt-broker.local", 1883),
        (
            ["", "--mqtt-host", "mqtt-broker.local", "--mqtt-port", "8883"],
            "mqtt-broker.local",
            8883,
        ),
    ],
)
def test__main(argv, expected_mqtt_host, expected_mqtt_port):
    with unittest.mock.patch("switchbot_mqtt._run") as run_mock, unittest.mock.patch(
        "sys.argv", argv
    ):
        # pylint: disable=protected-access
        switchbot_mqtt._main()
    run_mock.assert_called_once_with(
        mqtt_host=expected_mqtt_host, mqtt_port=expected_mqtt_port,
    )
