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
