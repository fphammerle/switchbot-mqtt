# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Control [SwitchBot Curtain](https://www.switch-bot.com/products/switchbot-curtain) motors
  via `OPEN`, `CLOSE`, and `STOP` on topic `homeassistant/cover/switchbot-curtain/aa:bb:cc:dd:ee:ff/set`

### Changed
- Docker image:
  - Upgrade `paho-mqtt` to no longer suppress exceptions occuring in mqtt callbacks
    ( https://github.com/eclipse/paho.mqtt.python/blob/v1.5.1/ChangeLog.txt#L4 )
  - Build stage: revert user after applying `chown` workaround for inter-stage copy

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

[Unreleased]: https://github.com/fphammerle/switchbot-mqtt/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/fphammerle/switchbot-mqtt/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/fphammerle/switchbot-mqtt/releases/tag/v0.1.0
