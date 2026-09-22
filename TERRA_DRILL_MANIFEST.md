# TERRA-CORE-DRILL — TERRA_DRILL_MANIFEST

> Rapport généré par `core_main.py`. Il s'agit d'un banc logiciel
> paramétrique et non d'une validation de faisabilité d'un forage réel.

## Identité du run

- Run ID : `20260922T180227Z`
- Généré UTC : `2026-09-22T18:02:27.789916+00:00`
- Profondeur initiale : **35,000.0 m**
- Profondeur finale : **6,371,000.0 m**
- Échantillons : **48** (générateur, sans liste de profil)
- Capteur Thermal Lock : **1.75 m** en amont de la tête

## Contrat mémoire et exécution

- Géométrie du blindage : blocs NumPy alternés, aucune matrice globale.
- Agrégation des capteurs : statistiques de Welford et historique borné.
- Checkpoint : écriture JSON atomique depuis la boucle principale, sans tâche de fond.
- Fichier checkpoint : `TERRA_DRILL_CHECKPOINT.json` (6 écriture(s))
- Aucun rendu 3-D et aucune simulation physique longue ne sont lancés.

## Blindage en tungstène — 10 couches

- Densité nominale : **19.25 g/cm³**
- Densité cible : **3.85 g/cm³**
- Porosité théorique cible : **80.00 %**
- Fraction solide modélisée : **20.00 %**
- Densité issue du raster : **3.849 g/cm³**
- Écart à la cible : **-0.001 g/cm³**
- Réduction massique nominale : **80.00 %**
- Maille : 100 nm, paroi 7.42 nm, 64 pixels/maille

### Transfert thermique de Fourier

- Température initiale : **5500.0 °C**
- Température de bord : **20.0 °C**
- Temps estimé vers la cible : **5.93 s**
- Température médiane après cooldown : **1000.00 °C**
- Flux de surface à cet instant : **5,326,257.26 W/m²**
- Diffusivité utilisée : **3.3539e-04 m²/s**

## Traversée paramétrique

| Phase | Points |
|---|---:|
| manteau_silicate | 22 |
| noyau_externe_liquide_fer_nickel | 16 |
| noyau_interne_fer_nickel | 10 |

- Points Thermal Lock : **35**
- Trames capteurs acceptées : **96**
- Trames capteurs rejetées : **0**

### Derniers états échantillonnés

| Index | Profondeur (m) | Phase | T (°C) | P (GPa) | ω (rad/s) | Débit (kg/s) | Lock |
|---:|---:|---|---:|---:|---:|---:|:---:|
| 36 | 4,888,106.4 | noyau_externe_liquide_fer_nickel | 4,783.0 | 275.98 | 0.000 | 40.000 | ACTIF |
| 37 | 5,022,914.9 | noyau_externe_liquide_fer_nickel | 4,893.6 | 283.62 | 0.000 | 40.000 | ACTIF |
| 38 | 5,157,723.4 | noyau_interne_fer_nickel | 5,004.3 | 291.26 | 0.000 | 40.000 | ACTIF |
| 39 | 5,292,531.9 | noyau_interne_fer_nickel | 5,114.9 | 298.89 | 0.000 | 40.000 | ACTIF |
| 40 | 5,427,340.4 | noyau_interne_fer_nickel | 5,225.5 | 306.53 | 0.000 | 40.000 | ACTIF |
| 41 | 5,562,148.9 | noyau_interne_fer_nickel | 5,336.2 | 314.17 | 0.000 | 40.000 | ACTIF |
| 42 | 5,696,957.4 | noyau_interne_fer_nickel | 5,446.8 | 321.81 | 0.000 | 40.000 | ACTIF |
| 43 | 5,831,766.0 | noyau_interne_fer_nickel | 5,557.4 | 329.45 | 0.000 | 40.000 | ACTIF |
| 44 | 5,966,574.5 | noyau_interne_fer_nickel | 5,668.1 | 337.09 | 0.000 | 40.000 | ACTIF |
| 45 | 6,101,383.0 | noyau_interne_fer_nickel | 5,778.7 | 344.72 | 0.000 | 40.000 | ACTIF |
| 46 | 6,236,191.5 | noyau_interne_fer_nickel | 5,889.4 | 352.36 | 0.000 | 40.000 | ACTIF |
| 47 | 6,371,000.0 | noyau_interne_fer_nickel | 6,000.0 | 360.00 | 0.000 | 40.000 | ACTIF |

## Données de capteurs

```json
{
  "frames_ingested": 96,
  "frames_rejected": 0,
  "last_sequence": 47,
  "history_limit": 256,
  "recent": [
    {
      "type": "magnetometer",
      "sequence": 0,
      "timestamp_ms": 0,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 0,
      "timestamp_ms": 0,
      "pressure_pa": 1000000000.0,
      "pressure_gpa": 1.0
    },
    {
      "type": "magnetometer",
      "sequence": 1,
      "timestamp_ms": 1000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 1,
      "timestamp_ms": 1000,
      "pressure_pa": 8638298112.0,
      "pressure_gpa": 8.638298112
    },
    {
      "type": "magnetometer",
      "sequence": 2,
      "timestamp_ms": 2000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 2,
      "timestamp_ms": 2000,
      "pressure_pa": 16276595712.0,
      "pressure_gpa": 16.276595712
    },
    {
      "type": "magnetometer",
      "sequence": 3,
      "timestamp_ms": 3000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 3,
      "timestamp_ms": 3000,
      "pressure_pa": 23914893312.0,
      "pressure_gpa": 23.914893312
    },
    {
      "type": "magnetometer",
      "sequence": 4,
      "timestamp_ms": 4000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 4,
      "timestamp_ms": 4000,
      "pressure_pa": 31553191936.0,
      "pressure_gpa": 31.553191936
    },
    {
      "type": "magnetometer",
      "sequence": 5,
      "timestamp_ms": 5000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 5,
      "timestamp_ms": 5000,
      "pressure_pa": 39191490560.0,
      "pressure_gpa": 39.19149056
    },
    {
      "type": "magnetometer",
      "sequence": 6,
      "timestamp_ms": 6000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 6,
      "timestamp_ms": 6000,
      "pressure_pa": 46829789184.0,
      "pressure_gpa": 46.829789184
    },
    {
      "type": "magnetometer",
      "sequence": 7,
      "timestamp_ms": 7000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 7,
      "timestamp_ms": 7000,
      "pressure_pa": 54468083712.0,
      "pressure_gpa": 54.468083712
    },
    {
      "type": "magnetometer",
      "sequence": 8,
      "timestamp_ms": 8000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 8,
      "timestamp_ms": 8000,
      "pressure_pa": 62106382336.0,
      "pressure_gpa": 62.106382336
    },
    {
      "type": "magnetometer",
      "sequence": 9,
      "timestamp_ms": 9000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 9,
      "timestamp_ms": 9000,
      "pressure_pa": 69744680960.0,
      "pressure_gpa": 69.74468096
    },
    {
      "type": "magnetometer",
      "sequence": 10,
      "timestamp_ms": 10000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 10,
      "timestamp_ms": 10000,
      "pressure_pa": 77382975488.0,
      "pressure_gpa": 77.382975488
    },
    {
      "type": "magnetometer",
      "sequence": 11,
      "timestamp_ms": 11000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 11,
      "timestamp_ms": 11000,
      "pressure_pa": 85021278208.0,
      "pressure_gpa": 85.021278208
    },
    {
      "type": "magnetometer",
      "sequence": 12,
      "timestamp_ms": 12000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 12,
      "timestamp_ms": 12000,
      "pressure_pa": 92659572736.0,
      "pressure_gpa": 92.659572736
    },
    {
      "type": "magnetometer",
      "sequence": 13,
      "timestamp_ms": 13000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 13,
      "timestamp_ms": 13000,
      "pressure_pa": 100297875456.0,
      "pressure_gpa": 100.297875456
    },
    {
      "type": "magnetometer",
      "sequence": 14,
      "timestamp_ms": 14000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 14,
      "timestamp_ms": 14000,
      "pressure_pa": 107936169984.0,
      "pressure_gpa": 107.936169984
    },
    {
      "type": "magnetometer",
      "sequence": 15,
      "timestamp_ms": 15000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 15,
      "timestamp_ms": 15000,
      "pressure_pa": 115574464512.0,
      "pressure_gpa": 115.574464512
    },
    {
      "type": "magnetometer",
      "sequence": 16,
      "timestamp_ms": 16000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 16,
      "timestamp_ms": 16000,
      "pressure_pa": 123212767232.0,
      "pressure_gpa": 123.212767232
    },
    {
      "type": "magnetometer",
      "sequence": 17,
      "timestamp_ms": 17000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 17,
      "timestamp_ms": 17000,
      "pressure_pa": 130851061760.0,
      "pressure_gpa": 130.85106176
    },
    {
      "type": "magnetometer",
      "sequence": 18,
      "timestamp_ms": 18000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 18,
      "timestamp_ms": 18000,
      "pressure_pa": 138489364480.0,
      "pressure_gpa": 138.48936448
    },
    {
      "type": "magnetometer",
      "sequence": 19,
      "timestamp_ms": 19000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 19,
      "timestamp_ms": 19000,
      "pressure_pa": 146127667200.0,
      "pressure_gpa": 146.1276672
    },
    {
      "type": "magnetometer",
      "sequence": 20,
      "timestamp_ms": 20000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 20,
      "timestamp_ms": 20000,
      "pressure_pa": 153765953536.0,
      "pressure_gpa": 153.765953536
    },
    {
      "type": "magnetometer",
      "sequence": 21,
      "timestamp_ms": 21000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 21,
      "timestamp_ms": 21000,
      "pressure_pa": 161404256256.0,
      "pressure_gpa": 161.404256256
    },
    {
      "type": "magnetometer",
      "sequence": 22,
      "timestamp_ms": 22000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 37.416572922517254
    },
    {
      "type": "piezo_pressure",
      "sequence": 22,
      "timestamp_ms": 22000,
      "pressure_pa": 169042558976.0,
      "pressure_gpa": 169.042558976
    },
    {
      "type": "magnetometer",
      "sequence": 23,
      "timestamp_ms": 23000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 37.416572922517254
    },
    {
      "type": "piezo_pressure",
      "sequence": 23,
      "timestamp_ms": 23000,
      "pressure_pa": 176680845312.0,
      "pressure_gpa": 176.680845312
    },
    {
      "type": "magnetometer",
      "sequence": 24,
      "timestamp_ms": 24000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 37.416572922517254
    },
    {
      "type": "piezo_pressure",
      "sequence": 24,
      "timestamp_ms": 24000,
      "pressure_pa": 184319148032.0,
      "pressure_gpa": 184.319148032
    },
    {
      "type": "magnetometer",
      "sequence": 25,
      "timestamp_ms": 25000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 37.416572922517254
    },
    {
      "type": "piezo_pressure",
      "sequence": 25,
      "timestamp_ms": 25000,
      "pressure_pa": 191957450752.0,
      "pressure_gpa": 191.957450752
    },
    {
      "type": "magnetometer",
      "sequence": 26,
      "timestamp_ms": 26000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 37.416572922517254
    },
    {
      "type": "piezo_pressure",
      "sequence": 26,
      "timestamp_ms": 26000,
      "pressure_pa": 199595737088.0,
      "pressure_gpa": 199.595737088
    },
    {
      "type": "magnetometer",
      "sequence": 27,
      "timestamp_ms": 27000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 37.416572922517254
    },
    {
      "type": "piezo_pressure",
      "sequence": 27,
      "timestamp_ms": 27000,
      "pressure_pa": 207234039808.0,
      "pressure_gpa": 207.234039808
    },
    {
      "type": "magnetometer",
      "sequence": 28,
      "timestamp_ms": 28000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 37.416572922517254
    },
    {
      "type": "piezo_pressure",
      "sequence": 28,
      "timestamp_ms": 28000,
      "pressure_pa": 214872342528.0,
      "pressure_gpa": 214.872342528
    },
    {
      "type": "magnetometer",
      "sequence": 29,
      "timestamp_ms": 29000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 37.416572922517254
    },
    {
      "type": "piezo_pressure",
      "sequence": 29,
      "timestamp_ms": 29000,
      "pressure_pa": 222510645248.0,
      "pressure_gpa": 222.510645248
    },
    {
      "type": "magnetometer",
      "sequence": 30,
      "timestamp_ms": 30000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 37.416572922517254
    },
    {
      "type": "piezo_pressure",
      "sequence": 30,
      "timestamp_ms": 30000,
      "pressure_pa": 230148931584.0,
      "pressure_gpa": 230.148931584
    },
    {
      "type": "magnetometer",
      "sequence": 31,
      "timestamp_ms": 31000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 37.416572922517254
    },
    {
      "type": "piezo_pressure",
      "sequence": 31,
      "timestamp_ms": 31000,
      "pressure_pa": 237787234304.0,
      "pressure_gpa": 237.787234304
    },
    {
      "type": "magnetometer",
      "sequence": 32,
      "timestamp_ms": 32000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 37.416572922517254
    },
    {
      "type": "piezo_pressure",
      "sequence": 32,
      "timestamp_ms": 32000,
      "pressure_pa": 245425537024.0,
      "pressure_gpa": 245.425537024
    },
    {
      "type": "magnetometer",
      "sequence": 33,
      "timestamp_ms": 33000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 37.416572922517254
    },
    {
      "type": "piezo_pressure",
      "sequence": 33,
      "timestamp_ms": 33000,
      "pressure_pa": 253063823360.0,
      "pressure_gpa": 253.06382336
    },
    {
      "type": "magnetometer",
      "sequence": 34,
      "timestamp_ms": 34000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 37.416572922517254
    },
    {
      "type": "piezo_pressure",
      "sequence": 34,
      "timestamp_ms": 34000,
      "pressure_pa": 260702126080.0,
      "pressure_gpa": 260.70212608
    },
    {
      "type": "magnetometer",
      "sequence": 35,
      "timestamp_ms": 35000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 37.416572922517254
    },
    {
      "type": "piezo_pressure",
      "sequence": 35,
      "timestamp_ms": 35000,
      "pressure_pa": 268340428800.0,
      "pressure_gpa": 268.3404288
    },
    {
      "type": "magnetometer",
      "sequence": 36,
      "timestamp_ms": 36000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 37.416572922517254
    },
    {
      "type": "piezo_pressure",
      "sequence": 36,
      "timestamp_ms": 36000,
      "pressure_pa": 275978715136.0,
      "pressure_gpa": 275.978715136
    },
    {
      "type": "magnetometer",
      "sequence": 37,
      "timestamp_ms": 37000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 37.416572922517254
    },
    {
      "type": "piezo_pressure",
      "sequence": 37,
      "timestamp_ms": 37000,
      "pressure_pa": 283617034240.0,
      "pressure_gpa": 283.61703424
    },
    {
      "type": "magnetometer",
      "sequence": 38,
      "timestamp_ms": 38000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 38,
      "timestamp_ms": 38000,
      "pressure_pa": 291255320576.0,
      "pressure_gpa": 291.255320576
    },
    {
      "type": "magnetometer",
      "sequence": 39,
      "timestamp_ms": 39000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 39,
      "timestamp_ms": 39000,
      "pressure_pa": 298893606912.0,
      "pressure_gpa": 298.893606912
    },
    {
      "type": "magnetometer",
      "sequence": 40,
      "timestamp_ms": 40000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 40,
      "timestamp_ms": 40000,
      "pressure_pa": 306531926016.0,
      "pressure_gpa": 306.531926016
    },
    {
      "type": "magnetometer",
      "sequence": 41,
      "timestamp_ms": 41000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 41,
      "timestamp_ms": 41000,
      "pressure_pa": 314170212352.0,
      "pressure_gpa": 314.170212352
    },
    {
      "type": "magnetometer",
      "sequence": 42,
      "timestamp_ms": 42000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 42,
      "timestamp_ms": 42000,
      "pressure_pa": 321808498688.0,
      "pressure_gpa": 321.808498688
    },
    {
      "type": "magnetometer",
      "sequence": 43,
      "timestamp_ms": 43000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 43,
      "timestamp_ms": 43000,
      "pressure_pa": 329446817792.0,
      "pressure_gpa": 329.446817792
    },
    {
      "type": "magnetometer",
      "sequence": 44,
      "timestamp_ms": 44000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 44,
      "timestamp_ms": 44000,
      "pressure_pa": 337085104128.0,
      "pressure_gpa": 337.085104128
    },
    {
      "type": "magnetometer",
      "sequence": 45,
      "timestamp_ms": 45000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 45,
      "timestamp_ms": 45000,
      "pressure_pa": 344723390464.0,
      "pressure_gpa": 344.723390464
    },
    {
      "type": "magnetometer",
      "sequence": 46,
      "timestamp_ms": 46000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 46,
      "timestamp_ms": 46000,
      "pressure_pa": 352361709568.0,
      "pressure_gpa": 352.361709568
    },
    {
      "type": "magnetometer",
      "sequence": 47,
      "timestamp_ms": 47000,
      "field_magnitude_t": 3.741657292251725e-05,
      "convection_proxy": 7.48331458450345
    },
    {
      "type": "piezo_pressure",
      "sequence": 47,
      "timestamp_ms": 47000,
      "pressure_pa": 359999995904.0,
      "pressure_gpa": 359.999995904
    }
  ],
  "statistics": {
    "field_magnitude_t": {
      "count": 48,
      "mean": 3.741657292251725e-05,
      "variance": 0.0,
      "standard_deviation": 0.0,
      "minimum": 3.741657292251725e-05,
      "maximum": 3.741657292251725e-05
    },
    "convection_proxy": {
      "count": 48,
      "mean": 17.461067363841387,
      "variance": 203.3475074565158,
      "standard_deviation": 14.259996755136932,
      "minimum": 7.48331458450345,
      "maximum": 37.416572922517254
    },
    "pressure_pa": {
      "count": 48,
      "mean": 180499999861.3333,
      "variance": 1.1435344425468322e+22,
      "standard_deviation": 106936169865.33752,
      "minimum": 1000000000.0,
      "maximum": 359999995904.0
    },
    "spectral_olivine_index": {
      "count": 0,
      "mean": 0.0,
      "variance": 0.0,
      "standard_deviation": 0.0,
      "minimum": 0.0,
      "maximum": 0.0
    },
    "spectral_pyroxene_index": {
      "count": 0,
      "mean": 0.0,
      "variance": 0.0,
      "standard_deviation": 0.0,
      "minimum": 0.0,
      "maximum": 0.0
    },
    "spectral_feldspar_index": {
      "count": 0,
      "mean": 0.0,
      "variance": 0.0,
      "standard_deviation": 0.0,
      "minimum": 0.0,
      "maximum": 0.0
    }
  }
}
```

## Limites et actions de qualification

1. Remplacer le profil linéaire par une table géophysique versionnée et traçable.
2. Calibrer les coefficients de commande sur un jumeau numérique vérifié puis sur banc instrumenté.
3. Ajouter une validation indépendante des bornes, de la perte de trames et du réarmement Thermal Lock.
4. Ne pas interpréter la géométrie de porosité comme une qualification mécanique du tungstène.

_Fin du manifeste._
