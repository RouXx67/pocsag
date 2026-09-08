#!/bin/bash
set -e
export PATH="$PATH:/usr/sbin:/sbin:/usr/local/sbin"

echo "========================================="
echo "  POCSAG v2 - Test de decodage radio"
echo "========================================="
echo ""

# 1. Check dongle
echo "[1/5] Detection du dongle RTL-SDR..."
lsusb 2>/dev/null | grep -qi "realtek\|rtl283" && echo "  OK: Dongle detecte" || echo "  WARN: Dongle non trouve par lsusb"

# 2. Check rtl_test
echo "[2/5] Test rtl_test (3s)..."
timeout 3 rtl_test -t 2>&1 | head -5 || echo "  FAIL: rtl_test error (may be in use)"

# 3. Kill existing processes
echo "[3/5] Arret des processus residuels..."
pkill -9 rtl_fm 2>/dev/null || true
pkill -9 multimon-ng 2>/dev/null || true
sleep 0.5
echo "  OK"

# 4. Test radio chain (5s)
echo "[4/5] Test chaine radio complete (8s)..."
timeout 8 sh -c 'rtl_fm -f 85.955M -M fm -s 176400 -r 22050 -l 0 -g 19.2 2>/dev/null | timeout 8 multimon-ng -t raw -a POCSAG512 -a POCSAG1200 -a POCSAG2400 -f alpha -' 2>&1 | tail -5
echo ""
echo "  Si vous voyez des lignes POCSAG1200: Address:... -> DECODAGE OK"
echo "  Si rien -> pas de signal sur cette frequence"
echo ""

# 5. Test API
echo "[5/5] Test API..."
curl -s http://localhost:8080/api/version 2>/dev/null && echo "  API: OK" || echo "  API: Service non joignable"
curl -s http://localhost:8080/api/radio/dongle 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  DONGLE: API non disponible"

echo ""
echo "========================================="
echo "  Test termine"
echo "========================================="