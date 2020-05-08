Use `sudo hcitool lescan`
or select device settings > 3 dots on top right in
[SwitchBot app](https://play.google.com/store/apps/details?id=com.theswitchbot.switchbot)
to determine the **mac address**.

## Home Assistant 🏡

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
