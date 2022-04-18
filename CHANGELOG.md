# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [3.2.0] - 2022-04-18
### Added
- command-line option `--mqtt-topic-prefix`

## [3.1.0] - 2022-04-02
### Added
- command-line option `--mqtt-enable-tls`
- command-line option `--mqtt-disable-tls` (enabled by default)

### Deprecated
- invocation without `--mqtt-enable-tls` and `--mqtt-disable-tls`

## [3.0.0] - 2022-02-05
### Added
- MQTT messages on topic `homeassistant/cover/switchbot-curtain/MAC_ADDRESS/position/set-percent`
  trigger command to set curtain motors' position (payload: decimal integer in range `[0, 100]`)
- support `PySwitchbot` `v0.11.0` and `v0.12.0`

### Removed
- compatibility with `python3.6`
- no longer report button automator's battery percentage on deprecated topic
  `homeassistant/cover/switchbot/+/battery-percentage`
  (use `homeassistant/switch/switchbot/+/battery-percentage` instead, see `v2.1.0`)

## [2.2.0] - 2021-10-23
### Added
- MQTT messages on topic `homeassistant/switch/switchbot/MAC_ADDRESS/request-device-info`
  and `homeassistant/cover/switchbot-curtain/MAC_ADDRESS/request-device-info` trigger
  update and reporting of device information (battery level, and curtains' position).
  Requires `--fetch-device-info`.

## [2.1.0] - 2021-10-19
### Added
- `--fetch-device-info` can alternatively be enabled by assigning a non-empty value
  to the environment variable `FETCH_DEVICE_INFO`
- battery level of button automators will additionally be reported on topic
  `homeassistant/switch/switchbot/MAC_ADDRESS/battery-percentage`
  (old topic kept for downward compatibility)

## [2.0.0] - 2021-10-16
### Added
- command-line option `--fetch-device-info` enables battery level reports on topics
  `homeassistant/cover/{switchbot,switchbot-curtain}/MAC_ADDRESS/battery-percentage`
  after every command.
- option `--debug` to change log level to `DEBUG`

### Changed
- changed default log level from `DEBUG` to `INFO`
- shortened log format (revert with `--debug`)

### Removed
- compatibility with `python3.5`

## [1.1.0] - 2021-10-06
### Added
- command-line option `--fetch-device-info` enables reporting of curtain motors'
  position on topic  `homeassistant/cover/switchbot-curtain/MAC_ADDRESS/position`
  after sending stop command.

## [1.0.0] - 2021-07-25
### Added
- support for password-protected switchbot devices
  via optional command-line parameter `--device-password-file`
  (json file mapping mac addresses to the respective password)

## [0.7.0] - 2021-07-09
### Added
- command-line parameter `--retries` to alter maximum number of attempts to send a command
  to a SwitchBot device (default unchanged)

### Fixed
- dockerfile: split `pipenv install` into two stages to speed up image builds
- dockerfile: `chmod` files copied from host to no longer require `o=rX` perms on host
- dockerfile: add registry to base image specifier for `podman build`
- dockerfile: add `--force` flag to `rm` invocation to avoid interactive questions while running `podman build`

## [0.6.0] - 2020-12-19
### Added
- Control [SwitchBot Curtain](https://www.switch-bot.com/products/switchbot-curtain) motors
  via `OPEN`, `CLOSE`, and `STOP` on topic `homeassistant/cover/switchbot-curtain/aa:bb:cc:dd:ee:ff/set`

### Changed
- Docker image:
  - Upgrade `paho-mqtt` to no longer suppress exceptions occuring in mqtt callbacks
    ( https://github.com/eclipse/paho.mqtt.python/blob/v1.5.1/ChangeLog.txt#L4 )
  - Build stage: revert user after applying `chown` workaround for inter-stage copy
- Log format: added name of logger between level and message

## [0.5.0] - 2020-11-22
### Added
- Docker image: support parametrization via environment variables
  (`MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME` & `MQTT_PASSWORD`)

## [0.4.1] - 2020-06-18
### Fixed
- Compatibility with python3.5:
  - Replaced [PEP526](https://www.python.org/dev/peps/pep-0526/#abstract)-style variable type hint
    with [PEP484](https://www.python.org/dev/peps/pep-0484/)-compatible
  - Tests: Fixed `AttributeError` due to unavailable `MagicMock.assert_called_once`

## [0.4.0] - 2020-06-14
### Added
- Added command line parameter `--mqtt-password-file`

### Fixed
- Docker build: fix `pipenv` failing to create cache

## [0.3.0] - 2020-05-08
### Added
- Publish new state to `homeassistant/switch/switchbot/MAC_ADDRESS/state` on success

## [0.2.0] - 2020-05-08
### Added
- Added command line parameters `--mqtt-username` and `--mqtt-password`

### Fixed
- Fixed executable name in command line help
- Docker: no longer require build arg `SWITCHBOT_MQTT_VERSION`
  (fixes auto build on hub.docker.com)

## [0.1.0] - 2020-05-08
### Added
- Subscribe to `homeassistant/switch/switchbot/+/set`.
  Handle `ON` and `OFF` messages.

[Unreleased]: https://github.com/fphammerle/switchbot-mqtt/compare/v3.2.0...HEAD
[3.2.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v3.1.0...v3.2.0
[3.1.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v2.2.0...v3.0.0
[2.2.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v1.1.0...v2.0.0
[1.1.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v0.7.0...v1.0.0
[0.7.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/fphammerle/switchbot-mqtt/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/fphammerle/switchbot-mqtt/releases/tag/v0.1.0
