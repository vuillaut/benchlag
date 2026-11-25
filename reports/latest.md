# Retard de Mistral Large 4 sur Claude Opus

Calculé le 2026-11-25 à partir de l'instantané Epoch AI `2026-11-25` (données sous licence CC BY 4.0, [epoch.ai/benchmarks](https://epoch.ai/benchmarks)).

## Résultat

- **Indice composite ECI** : Mistral Large 4 (2026-10-29) obtient 154.6. La lignée Claude Opus a atteint ce niveau vers le **2026-01-07**, soit un retard de **9.7 mois** (IC 90 % : 7.1 à 11.0 mois, 500 tirages bootstrap).
  - En versions réelles : entre 8.7 mois (première version d'Opus au-dessus) et 11.1 mois (dernière version en dessous).
- **Benchmark par benchmark** : médiane 8.5 mois (IC 90 % : 7.8 à 10.4) sur 15 benchmarks.
  - Sur les seuls benchmarks bien encadrés (10) : médiane 7.9 mois (IC 90 % : 6.4 à 8.5).
  - Sans repli sur la preview (6 benchmarks) : médiane 8.5 mois (IC 90 % : 7.5 à 17.0).
- Pour situer : retard sur la frontière tous laboratoires (meilleur ECI publié à chaque date) : 10.6 mois.

![ECI](eci_lag.png)

## Détail par benchmark

Score cible = meilleure configuration publiée. *Retard* = date de sortie de la cible moins la date interpolée où la frontière Opus atteint ce score. *Bornes* = retard calculé sur la première version d'Opus au-dessus / la dernière en dessous.

| Benchmark | Variante cible | Score | Meilleur Opus | Statut | Retard (mois) | Bornes | Retenu |
|---|---|---:|---:|---|---:|---|---|
| SimpleQA Verified | Mistral Large 4 | 0.224 | 0.722 | atteint | 25.8 | 11.1 – 32.0 | oui (encadrement 21 mois) |
| LMCA | Mistral Large 4 Preview | 0.421 | 0.803 | atteint | 17.6 | 16.5 – 31.2 | oui (encadrement 15 mois) |
| Mystery Game Puzzles | Mistral Large 4 | 0.119 | 0.681 | sous la 1re version | ≥ 14.8 | 14.8 – – | oui |
| DTBench | Mistral Large 4 Preview | 0.804 | 0.982 | atteint | 11.1 | 10.4 – 14.0 | oui |
| ProofBench | Mistral Large 4 Preview | 0.100 | 1.000 | sous la 1re version | ≥ 10.4 | 10.4 – – | oui |
| GPQA diamond | Mistral Large 4 | 0.905 | 0.959 | atteint | 8.9 | 8.7 – 11.1 | oui |
| WeirdML v3 | Mistral Large 4 Preview | 0.131 | 0.554 | atteint | 8.9 | 2.4 – 10.4 | oui (encadrement 8 mois) |
| FrontierMath-Tiers-1-3-v2-Private | Mistral Large 4 Preview | 0.617 | 0.960 | atteint | 8.5 | 8.0 – 10.4 | oui |
| Furniture Assembly | Mistral Large 4 | 0.012 | 0.762 | atteint | 8.1 | 6.4 – 8.7 | oui |
| FrontierMath-Tier-4-v2-Private | Mistral Large 4 Preview | 0.268 | 0.950 | atteint | 8.0 | 8.0 – 10.4 | oui |
| Chess Puzzles | Mistral Large 4 | 0.253 | 0.653 | atteint | 7.8 | 6.4 – 8.7 | oui |
| EBR-bench | Mistral Large 4 | 0.181 | 0.714 | atteint | 6.9 | 6.4 – 8.7 | oui |
| MirrorCode | Mistral Large 4 Preview | 0.400 | 0.956 | atteint | 6.4 | 5.7 – 8.0 | oui |
| FrontierCode | Mistral Large 4 Preview | 0.394 | 0.546 | atteint | 5.5 | 4.3 – 5.7 | oui |
| Surface Evolver Bench | Mistral Large 4 Preview | 0.281 | 0.875 | sous la 1re version | ≥ 4.3 | 4.3 – – | non (<2 Opus) |
| APEX-Agents | Mistral Large 4 Preview | 0.516 | 0.735 | atteint | 4.0 | 2.4 – 4.3 | oui |
| OTIS Mock AIME 2024-2025 | Mistral Large 4 | 0.994 | 1.000 | atteint | 2.2 | 1.2 – 3.2 | non (saturé) |

## Trajectoire ECI de la référence

| Modèle | Sortie | ECI | IC 90 % |
|---|---|---:|---|
| Claude 3 Opus | 2024-02-29 | 125.6 | 122.5 – 128.3 |
| Claude Opus 4 | 2025-05-22 | 142.8 | 141.3 – 144.4 |
| Claude Opus 4.1 | 2025-08-05 | 144.8 | 143.0 – 146.5 |
| Claude Opus 4.5 | 2025-11-24 | 151.9 | 150.3 – 153.4 |
| Claude Opus 4.6 | 2026-02-05 | 156.3 | 154.6 – 158.3 |
| Claude Opus 4.7 | 2026-04-16 | 157.5 | 155.6 – 159.6 |
| Claude Opus 4.8 | 2026-05-28 | 159.9 | 157.8 – 162.2 |
| Claude Opus 5 | 2026-07-24 | 164.7 | 162.3 – 167.5 |
| Claude Opus 5.5 | 2026-09-22 | 168.7 | 165.9 – 172.0 |

Méthode complète : voir `PROTOCOLE.md`.
