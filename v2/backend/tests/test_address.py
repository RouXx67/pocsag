import pytest
from app.services.address import extract_address


def test_avp_extract():
    msg = "AVP VL RUE DE LA GARE STRASBOURG"
    assert extract_address(msg) == "VL RUE DE LA GARE STRASBOURG"


def test_sap_extract():
    msg = "SAP VERT A DOMICILE VSAV001 BENFELD 7C RUE PETIT REMPART"
    addr = extract_address(msg)
    assert "BENFELD" in addr
    assert "RUE PETIT REMPART" in addr


def test_feu_extract():
    msg = "FEU DE CHAUME FPT001 STRASBOURG 12 RUE DE LA GARE"
    addr = extract_address(msg)
    assert "12 RUE DE LA GARE" in addr
    assert "STRASBOURG" in addr


def test_engin_removed():
    msg = "SAP VSAV001.COND BENFELD 7C RUE PETIT REMPART"
    addr = extract_address(msg)
    assert "VSAV001" not in addr


def test_city_first_pattern():
    msg = "THANN 12 AVENUE DE LA REPUBLIQUE"
    addr = extract_address(msg)
    assert "12 AVENUE DE LA REPUBLIQUE" in addr
    assert "THANN" in addr


def test_slash_fallback():
    msg = "AVP / STRASBOURG / 15 RUE DES FLEURS"
    addr = extract_address(msg)
    assert "STRASBOURG" in addr


def test_empty():
    assert extract_address("") == ""


def test_prefixes():
    msg = "RECONNAISSANCE RUE PRINCIPALE COLMAR"
    addr = extract_address(msg)
    assert "RUE PRINCIPALE" in addr


def test_no_address():
    msg = "TEST SIMPLE MESSAGE SANS ADRESSE"
    assert extract_address(msg) == msg