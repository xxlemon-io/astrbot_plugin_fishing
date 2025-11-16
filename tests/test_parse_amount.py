import pytest
from astrbot_plugin_fishing.utils import parse_amount


def test_parse_plain_number():
    assert parse_amount("1000") == 1000
    assert parse_amount("1,000,000") == 1000000


def test_parse_arabic_with_unit():
    assert parse_amount("1万") == 10000
    assert parse_amount("1千万") == 10000000
    assert parse_amount("13百万") == 13000000


def test_parse_chinese_numbers():
    assert parse_amount("一") == 1
    assert parse_amount("十") == 10
    assert parse_amount("一百二十三") == 123
    assert parse_amount("一千三百万") == 13000000
    assert parse_amount("两万") == 20000


def test_invalid():
    with pytest.raises(ValueError):
        parse_amount("")
    with pytest.raises(ValueError):
        parse_amount("abc")
