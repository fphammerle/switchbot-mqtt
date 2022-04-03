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

import enum
import logging
import queue  # pylint: disable=unused-import; in type hint
import re
import typing

_MAC_ADDRESS_REGEX = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")


def _mac_address_valid(mac_address: str) -> bool:
    return _MAC_ADDRESS_REGEX.match(mac_address.lower()) is not None


class _MQTTTopicPlaceholder(enum.Enum):
    MAC_ADDRESS = "MAC_ADDRESS"


_MQTTTopicLevel = typing.Union[str, _MQTTTopicPlaceholder]


def _join_mqtt_topic_levels(
    *,
    topic_prefix: str,
    topic_levels: typing.Iterable[_MQTTTopicLevel],
    mac_address: str,
) -> str:
    return topic_prefix + "/".join(
        mac_address if l == _MQTTTopicPlaceholder.MAC_ADDRESS else typing.cast(str, l)
        for l in topic_levels
    )


def _parse_mqtt_topic(
    *,
    topic: str,
    expected_prefix: str,
    expected_levels: typing.Collection[_MQTTTopicLevel],
) -> typing.Dict[_MQTTTopicPlaceholder, str]:
    if not topic.startswith(expected_prefix):
        raise ValueError(f"expected topic prefix {expected_prefix}, got topic {topic}")
    attrs: typing.Dict[_MQTTTopicPlaceholder, str] = {}
    topic_split = topic[len(expected_prefix) :].split("/")
    if len(topic_split) != len(expected_levels):
        raise ValueError(f"unexpected topic {topic}")
    for given_part, expected_part in zip(topic_split, expected_levels):
        if expected_part == _MQTTTopicPlaceholder.MAC_ADDRESS:
            attrs[_MQTTTopicPlaceholder(expected_part)] = given_part
        elif expected_part != given_part:
            raise ValueError(f"unexpected topic {topic}")
    return attrs


class _QueueLogHandler(logging.Handler):
    """
    logging.handlers.QueueHandler drops exc_info
    """

    # TypeError: 'type' object is not subscriptable
    def __init__(self, log_queue: "queue.Queue[logging.LogRecord]") -> None:
        self.log_queue = log_queue
        super().__init__()

    def emit(self, record: logging.LogRecord) -> None:
        self.log_queue.put(record)
