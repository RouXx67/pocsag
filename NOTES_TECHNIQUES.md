# Notes Techniques POCSAG Monitor

## Paramètres RTL-SDR optimisés

### Commande rtl_fm dans le service
```bash
rtl_fm -f 85.955M -f 173512.5k -M fm -s 176400 -r 22050 -E offset -l 0 -g 19.2
```

### Explication des paramètres

| Paramètre | Valeur | Description |
|-----------|--------|-------------|
| `-f 85.955M` | 85,955 MHz | Fréquence VHF Bas Sapeurs-Pompiers France |
| `-f 173512.5k` | 173,5125 MHz | Fréquence VHF Haut Sapeurs-Pompiers France |
| `-M fm` | FM | Mode de démodulation FM |
| `-s 176400` | 176,4 kHz | Taux d'échantillonnage (8 × 22050) |
| `-r 22050` | 22,05 kHz | Taux de rééchantillonnage de sortie |
| `-E offset` |  | Correction offset DC |
| `-l 0` | 0 dB | Pas de squelch automatique |
| `-g 19.2` | 19,2 dB | Gain RF optimal pour RTL-SDR |

### Paramètres multimon-ng

```bash
multimon-ng -t raw -a POCSAG512 -a POCSAG1200 -a POCSAG2400 -f alpha -
```

| Paramètre | Description |
|-----------|-------------|
| `-t raw` | Format d'entrée raw (depuis rtl_fm) |
| `-a POCSAG512` | Décodage POCSAG 512 bauds |
| `-a POCSAG1200` | Décodage POCSAG 1200 bauds |
| `-a POCSAG2400` | Décodage POCSAG 2400 bauds |
| `-f alpha` | Forcer l'affichage des caractères alphanumériques |
| `-` | Lecture depuis stdin (pipe) |

## Optimisations possibles

### Gain RTL-SDR
- **19.2 dB** : Bon compromis signal/bruit pour environnement urbain
- **Réduction** si saturation (signaux trop forts)
- **Augmentation** si réception faible (zone rurale)

### Test de gain optimal
```bash
# Test différents gains
for gain in 10 15 19.2 25 30; do
  echo "Test gain $gain dB"
  rtl_fm -f 85.955M -g $gain -s 22050 -r 22050 | multimon-ng -t raw -a POCSAG1200 - | head -20
done
```

### Fréquences alternatives France

| Service | Fréquence | Usage |
|---------|-----------|-------|
| 85,955 MHz | VHF Bas | SDIS Principal |
| 173,5125 MHz | VHF Haut | SDIS Secondaire |
| 85,935 MHz | VHF Bas | SDIS Certains départements |
| 173,4875 MHz | VHF Haut | SDIS Certains départements |

## Dépannage réception

### Vérification signal
```bash
# Test réception pure
rtl_test -t

# Test avec FFT pour voir le spectre
rtl_power -f 85.955M -g 19.2 -i 1

# Test décodage manuel
rtl_fm -f 85.955M -g 19.2 -s 22050 | multimon-ng -t raw -a POCSAG1200 -
```

### Problèmes courants

1. **Pas de réception** :
   - Vérifier antenne connectée
   - Tester avec `rtl_test -t`
   - Ajuster le gain

2. **Messages tronqués** :
   - Réduire le gain (saturation)
   - Vérifier l'antenne (adaptation 50Ω)

3. **Beaucoup de bruit** :
   - Éloigner des sources d'interférence
   - Utiliser une antenne directionnelle
   - Réduire le gain

## Structure antenne recommandée

### VHF Bas (85 MHz)
- **Dipôle** : 2 × 87 cm (λ/4)
- **Ground Plane** : 4 radians de 87 cm

### VHF Haut (173 MHz)  
- **Dipôle** : 2 × 43 cm (λ/4)
- **Ground Plane** : 4 radians de 43 cm

### Antenne large bande
- **Discone** : Couvre 80-180 MHz
- **Log-périodique** : Directionnelle, gain élevé