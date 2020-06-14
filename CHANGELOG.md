# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
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

[Unreleased]: https://github.com/fphammerle/switchbot-mqtt/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/fphammerle/switchbot-mqtt/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/fphammerle/switchbot-mqtt/releases/tag/v0.1.0
