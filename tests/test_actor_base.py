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

import paho.mqtt.client
import pytest

import switchbot_mqtt

# pylint: disable=protected-access


def test_abstract():
    with pytest.raises(TypeError, match=r"\babstract class\b"):
        # pylint: disable=abstract-class-instantiated
        switchbot_mqtt._MQTTControlledActor(mac_address=None)


def test_execute_command_abstract():
    class _ActorMock(switchbot_mqtt._MQTTControlledActor):
        def execute_command(
            self, mqtt_message_payload: bytes, mqtt_client: paho.mqtt.client.Client
        ) -> None:
            super().execute_command(
                mqtt_message_payload=mqtt_message_payload, mqtt_client=mqtt_client
            )

    actor = _ActorMock(mac_address=None)
    with pytest.raises(NotImplementedError):
        actor.execute_command(mqtt_message_payload=b"dummy", mqtt_client="dummy")
