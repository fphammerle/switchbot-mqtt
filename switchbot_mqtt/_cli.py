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

import argparse
import json
import logging
import os
import pathlib
import warnings

import switchbot

import switchbot_mqtt
from switchbot_mqtt._actors import _ButtonAutomator, _CurtainMotor

_MQTT_DEFAULT_PORT = 1883
_MQTT_DEFAULT_TLS_PORT = 8883

_LOGGER = logging.getLogger(__name__)


def _main() -> None:
    argparser = argparse.ArgumentParser(
        description="MQTT client controlling SwitchBot button automators, "
        "compatible with home-assistant.io's MQTT Switch platform"
    )
    argparser.add_argument("--mqtt-host", type=str, required=True)
    argparser.add_argument(
        "--mqtt-port",
        type=int,
        help=f"default {_MQTT_DEFAULT_PORT} ({_MQTT_DEFAULT_TLS_PORT} with --mqtt-enable-tls)",
    )
    mqtt_tls_argument_group = argparser.add_mutually_exclusive_group()
    mqtt_tls_argument_group.add_argument(
        "--mqtt-enable-tls",
        action="store_true",
        help="TLS will be enabled by default in the next major release",
    )
    mqtt_tls_argument_group.add_argument(  # for upward compatibility
        "--mqtt-disable-tls", action="store_true", help="Currently enabled by default"
    )
    argparser.add_argument("--mqtt-username", type=str)
    password_argument_group = argparser.add_mutually_exclusive_group()
    password_argument_group.add_argument("--mqtt-password", type=str)
    password_argument_group.add_argument(
        "--mqtt-password-file",
        type=pathlib.Path,
        metavar="PATH",
        dest="mqtt_password_path",
        help="Stripping trailing newline",
    )
    argparser.add_argument(
        "--mqtt-topic-prefix",
        metavar="PREFIX",
        default="homeassistant/",  # for historic reasons (change to empty string?)
        help="Default: %(default)s",
    )
    argparser.add_argument(
        "--device-password-file",
        type=pathlib.Path,
        metavar="PATH",
        dest="device_password_path",
        help="Path to json file mapping mac addresses of switchbot devices to passwords, e.g. "
        + json.dumps({"11:22:33:44:55:66": "password", "aa:bb:cc:dd:ee:ff": "secret"}),
    )
    argparser.add_argument(
        "--retries",
        dest="retry_count",
        type=int,
        default=switchbot.DEFAULT_RETRY_COUNT,
        help="Maximum number of attempts to send a command to a SwitchBot device"
        " (default: %(default)d)",
    )
    argparser.add_argument(
        "--fetch-device-info",
        action="store_true",
        help="Report devices' battery level on topic "
        + _ButtonAutomator.get_mqtt_battery_percentage_topic(
            prefix="[PREFIX]", mac_address="MAC_ADDRESS"
        )
        + " or, respectively, "
        + _CurtainMotor.get_mqtt_battery_percentage_topic(
            prefix="[PREFIX]", mac_address="MAC_ADDRESS"
        )
        + " after every command. Additionally report curtain motors' position on topic "
        + _CurtainMotor.get_mqtt_position_topic(
            prefix="[PREFIX]", mac_address="MAC_ADDRESS"
        )
        + " after executing stop commands."
        " When this option is enabled, the mentioned reports may also be requested"
        " by sending a MQTT message to the topic "
        + _ButtonAutomator.get_mqtt_update_device_info_topic(
            prefix="[PREFIX]", mac_address="MAC_ADDRESS"
        )
        + " or "
        + _CurtainMotor.get_mqtt_update_device_info_topic(
            prefix="[PREFIX]", mac_address="MAC_ADDRESS"
        )
        + ". This option can also be enabled by assigning a non-empty value to the"
        " environment variable FETCH_DEVICE_INFO."
        " [PREFIX] can be set via --mqtt-topic-prefix.",
    )
    argparser.add_argument("--debug", action="store_true")
    args = argparser.parse_args()
    # https://github.com/fphammerle/python-cc1101/blob/26d8122661fc4587ecc7c73df55b92d05cf98fe8/cc1101/_cli.py#L51
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s:%(levelname)s:%(name)s:%(funcName)s:%(message)s"
        if args.debug
        else "%(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    _LOGGER.debug("args=%r", args)
    if args.mqtt_port:
        mqtt_port = args.mqtt_port
    elif args.mqtt_enable_tls:
        mqtt_port = _MQTT_DEFAULT_TLS_PORT
    else:
        mqtt_port = _MQTT_DEFAULT_PORT
    if not args.mqtt_enable_tls and not args.mqtt_disable_tls:
        warnings.warn(
            "In switchbot-mqtt's next major release, TLS will be enabled by default"
            " (--mqtt-enable-tls)."
            " Please add --mqtt-disable-tls to your command for upward compatibility.",
            UserWarning,  # DeprecationWarning ignored by default
        )
    if args.mqtt_password_path:
        # .read_text() replaces \r\n with \n
        mqtt_password = args.mqtt_password_path.read_bytes().decode()
        if mqtt_password.endswith("\r\n"):
            mqtt_password = mqtt_password[:-2]
        elif mqtt_password.endswith("\n"):
            mqtt_password = mqtt_password[:-1]
    else:
        mqtt_password = args.mqtt_password
    if args.device_password_path:
        device_passwords = json.loads(args.device_password_path.read_text())
    else:
        device_passwords = {}
    switchbot_mqtt._run(  # pylint: disable=protected-access; internal
        mqtt_host=args.mqtt_host,
        mqtt_port=mqtt_port,
        mqtt_disable_tls=not args.mqtt_enable_tls,
        mqtt_username=args.mqtt_username,
        mqtt_password=mqtt_password,
        mqtt_topic_prefix=args.mqtt_topic_prefix,
        retry_count=args.retry_count,
        device_passwords=device_passwords,
        fetch_device_info=args.fetch_device_info
        # > In formal language theory, the empty string, [...], is the unique string of length zero.
        # https://en.wikipedia.org/wiki/Empty_string
        or bool(os.environ.get("FETCH_DEVICE_INFO")),
    )
