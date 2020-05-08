Use `sudo hcitool lescan`
or select device settings > 3 dots on top right in
[SwitchBot app](https://play.google.com/store/apps/details?id=com.theswitchbot.switchbot)
to determine the **mac address**.

## Home Assistant 🏡

### Rationale

Why not use the official [SwitchBot integration](https://www.home-assistant.io/integrations/switchbot/)?

I prefer not to share the host's **network stack** with home assistant
(more complicated network setup
and additional [netfilter](https://en.wikipedia.org/wiki/Netfilter) rules required for isolation).

Sadly, `docker run --network host` even requires `--userns host`:
> docker: Error response from daemon: cannot share the host's network namespace when user namespaces are enabled.

The docker image built from this repository works around this limitation
by explicitly running as an **unprivileged user**.

The [official home assistant image](https://hub.docker.com/r/homeassistant/home-assistant)
runs as `root`.
This imposes an unnecessary security risk, especially when disabling user namespace remapping
(`--userns host`).
See https://github.com/fphammerle/docker-home-assistant for an alternative.

### Setup

```yaml
# https://www.home-assistant.io/docs/mqtt/broker/#configuration-variables
mqtt:
  broker: BROKER_HOSTNAME_OR_IP_ADDRESS
  # credentials, additional options...

# https://www.home-assistant.io/integrations/switch.mqtt/#configuration-variables
switch:
- platform: mqtt
  name: some_name
  command_topic: homeassistant/switch/switchbot/aa:bb:cc:dd:ee:ff/set
  # http://materialdesignicons.com/
  icon: mdi:light-switch
```

## Docker

```sh
$ docker build -t switchbot-mqtt .
$ docker run --name spelunca_switchbot \
    --userns host --network host \
    switchbot-mqtt:latest \
    switchbot-mqtt --help
```

## Alternatives

* https://github.com/binsentsu/switchbot-ctrl
* https://github.com/OpenWonderLabs/python-host/blob/master/switchbot_py3.py
* https://gist.github.com/aerialist/163a5794e95ccd28dc023161324009ed
* https://gist.github.com/mugifly/a29f34df7de8960d72245fcb124513c7
