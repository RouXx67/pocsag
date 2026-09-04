import pytest
from app.services.parser import parse_line


def test_valid_pocsag_line():
    line = "POCSAG1200: Address: 0123456 Function: 1 Alpha: AVP VL RUE DE LA GARE STRASBOURG"
    result = parse_line(line)
    assert result is not None
    assert result["ric"] == "0123456"
    assert result["func"] == "1"
    assert result["message"] == "AVP VL RUE DE LA GARE STRASBOURG"
    assert "raw_line" in result


def test_valid_pocsag_512():
    line = "POCSAG512: Address: 0000001 Function: 2 Alpha: FEU DE CHAUME"
    result = parse_line(line)
    assert result is not None
    assert result["ric"] == "0000001"
    assert result["message"] == "FEU DE CHAUME"


def test_pocsag_2400():
    line = "POCSAG2400: Address: 9999999 Function: 0 Alpha: SAP VERT A DOMICILE"
    result = parse_line(line)
    assert result is not None
    assert result["ric"] == "9999999"
    assert result["message"] == "SAP VERT A DOMICILE"


def test_no_alpha():
    line = "POCSAG1200: Address: 1234567 Function: 3"
    result = parse_line(line)
    assert result is not None
    assert result["ric"] == "1234567"
    assert result["message"] == ""


def test_empty_line():
    assert parse_line("") is None


def test_junk_line():
    assert parse_line("some random text") is None


def test_multiple_spaces():
    line = "POCSAG1200:  Address:   0123456  Function:  1  Alpha:  TEST  MESSAGE"
    result = parse_line(line)
    assert result is not None
    assert result["ric"] == "0123456"
    assert result["message"] == "TEST  MESSAGE"