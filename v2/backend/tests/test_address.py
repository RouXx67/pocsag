"""
Test unitaire pour l'extracteur d'adresses.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.address import extract_address


def test_extract_address():
    # Cas réels des logs
    cases = [
        (
            "#G SAP JAUNE A DOMICILE VSAV001.CA BENFELD 4 RUE CHATEAU D EAU",
            "BENFELD 4 RUE CHATEAU D EAU"
        ),
        (
            "#G SAP JAUNE SUR VP/LP VSAV001.CA RHINAU 4 RUE BEAUMONT DU PERIGORD",
            "RHINAU 4 RUE BEAUMONT DU PERIGORD"
        ),
        (
            "#G SAP JAUNE A DOMICILE VSAV001.CA BOOFZHEIM 25 RUE COLMAR",
            "BOOFZHEIM 25 RUE COLMAR"
        ),
        (
            "#G CARENCE MOYENS PRIVES VSAV001.CA BENFELD 3 RUE ANCIENNE PORTE",
            "BENFELD 3 RUE ANCIENNE PORTE"
        ),
        # Cas sans numéro (exemple hypothétique)
        (
            "#G SAP JAUNE A DOMICILE VSAV001.CA BENFELD RUE CHATEAU D EAU",
            "BENFELD RUE CHATEAU D EAU"
        ),
        # Message sans adresse structurée -> retourne le texte nettoyé
        (
            "MESSAGE SANS ADRESSE STRUCTUREE",
            "MESSAGE SANS ADRESSE STRUCTUREE"
        ),
    ]

    failures = []
    for original, expected in cases:
        got = extract_address(original)
        if got != expected:
            failures.append((original, expected, got))

    if failures:
        for orig, exp, got in failures:
            print(f"❌ Échec sur : {orig}")
            print(f"   Attendu : {exp}")
            print(f"   Obtenu  : {got}")
        raise AssertionError(f"{len(failures)} test(s) en échec")
    else:
        print("✅ Tous les tests passent.")


if __name__ == "__main__":
    test_extract_address()