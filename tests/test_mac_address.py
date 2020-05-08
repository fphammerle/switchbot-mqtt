import pytest

import switchbot_mqtt


@pytest.mark.parametrize(
    ("mac_address", "valid"),
    [
        ("aa:bb:cc:dd:ee:ff", True),
        ("AA:BB:CC:DD:EE:FF", True),
        ("AA:12:34:45:67:89", True),
        ("aabbccddeeff", False),  # not supported by PySwitchbot
        ("aa:bb:cc:dd:ee:gg", False),
    ],
)
def test__mac_address_valid(mac_address, valid):
    # pylint: disable=protected-access
    assert switchbot_mqtt._mac_address_valid(mac_address) == valid
