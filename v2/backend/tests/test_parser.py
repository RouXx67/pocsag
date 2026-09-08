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
    assert parse_line("POCSAG1200: garbage data") is None


def test_multiple_spaces():
    line = "POCSAG1200:  Address:   0123456  Function:  1  Alpha:  TEST  MESSAGE"
    result = parse_line(line)
    assert result is not None
    assert result["ric"] == "0123456"
    assert result["message"] == "TEST  MESSAGE"


def test_real_world_sap():
    line = "POCSAG1200: Address: 0524823 Function: 1 Alpha: SAP VERT A DOMICILE VSAV001 RUE PRINCIPALE STRASBOURG"
    result = parse_line(line)
    assert result is not None
    assert result["ric"] == "0524823"
    assert "SAP" in result["message"]
    assert "STRASBOURG" in result["message"]


def test_real_world_feu():
    line = "POCSAG1200: Address: 0314792 Function: 1 Alpha: FEU DE CHAUME FPT001 COLMAR 12 RUE DES FLEURS"
    result = parse_line(line)
    assert result is not None
    assert result["ric"] == "0314792"
    assert "FEU" in result["message"]
    assert "COLMAR" in result["message"]


def test_real_world_avp():
    line = "POCSAG2400: Address: 0712356 Function: 0 Alpha: AVP VL CONTRE ARBRE VSAV003 SELESTAT D108"
    result = parse_line(line)
    assert result is not None
    assert result["ric"] == "0712356"
    assert "AVP" in result["message"]


def test_real_world_no_message():
    line = "POCSAG512: Address: 0099999 Function: 1"
    result = parse_line(line)
    assert result is not None
    assert result["ric"] == "0099999"
    assert result["message"] == ""


def test_unicode_accents():
    line = "POCSAG1200: Address: 0123456 Function: 1 Alpha: FEU DE CHAUME DESINCARCERATION STRASBOURG"
    result = parse_line(line)
    assert result is not None
    assert "DESINCARCERATION" in result["message"]


def test_newline_in_message():
    line = "POCSAG1200: Address: 0123456 Function: 1 Alpha: TEST\nLINE2"
    result = parse_line(line)
    assert result is not None
    assert result["ric"] == "0123456"
    assert "TEST" in result["message"]


def test_very_long_message():
    msg = "A" * 500
    line = f"POCSAG1200: Address: 0123456 Function: 1 Alpha: {msg}"
    result= parse_line(line)
    assert result is not None
    assert result["ric"] == "0123456"
    assert len(result["message"]) == 500