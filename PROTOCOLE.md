# Protocole : mesurer en mois le retard d'un modèle sur une lignée de référence

## Question

À quelle date la lignée de référence (ici Claude Opus) a-t-elle atteint le niveau du modèle cible (ici Mistral Large 4) ? Le retard est l'écart entre cette date et la sortie du modèle cible.

## Source des données

Une seule source, publique et mise à jour en continu : le hub de benchmarks d'Epoch AI (`https://epoch.ai/data/benchmark_data.zip`, licence CC BY 4.0). J'ai choisi cette source pour trois raisons :

1. Epoch fait tourner une bonne partie des benchmarks lui-même (GPQA, FrontierMath, OTIS AIME, Chess Puzzles…), avec le même harnais pour tous les modèles. Les chiffres annoncés par les labos ne servent pas.
2. Le fichier `processed_data_for_eci.csv` donne déjà un score par modèle et par benchmark, ramené sur [0, 1], avec la meilleure configuration de raisonnement de chaque modèle. Je n'ai pas à harmoniser des réglages « high », « xhigh » ou « 64k thinking » moi-même.
3. Epoch publie un indice composite, l'ECI (Epoch Capabilities Index), avec 500 tirages bootstrap. Cela donne une incertitude propre sur le résultat principal.

Chaque téléchargement est figé dans `data/raw/AAAA-MM-JJ/`, avec son empreinte SHA-256. Si le zip n'a pas changé, aucun nouvel instantané n'est créé.

## Méthode A : indice composite (résultat principal)

1. On prend l'ECI de chaque version d'Opus et sa date de sortie.
2. On ne garde que les **records** : les versions qui battent le meilleur ECI atteint jusque-là. Une version qui régresse ne fait pas reculer la lignée. Les modèles sortis le même jour comptent pour un seul point, le meilleur.
3. On cherche le point où la ligne qui relie ces records croise l'ECI du modèle cible, par interpolation linéaire dans le temps entre le dernier record sous la cible et le premier au-dessus.

Pourquoi les records seulement : si l'on interpolait entre deux modèles consécutifs quelconques, une référence dense (tous les labos, presque un modèle par semaine) donnerait des intervalles de quelques jours. On retomberait alors sur la date du premier modèle au-dessus, sans interpolation, alors qu'une lignée courte comme Opus serait interpolée sur plusieurs mois. Les deux chiffres ne seraient pas comparables. Avec les records, les deux cas suivent la même règle. Exemple : pour Mistral Large 4 face à tous les labos, l'interpolation se fait entre Gemini 3 Pro (18 novembre 2025, ECI 153,0) et GPT-5.2 Pro (11 décembre 2025, ECI 157,4). GPT-5.2, sorti le même jour que GPT-5.2 Pro, ne compte pas à part.
4. Retard = date de sortie de la cible − date de croisement.
5. On répète les étapes 2 à 4 sur les 500 tirages bootstrap d'Epoch. Les centiles 5 et 95 donnent l'intervalle à 90 %. L'incertitude porte à la fois sur le score de la cible et sur ceux d'Opus.

Le rapport donne aussi deux bornes sans interpolation : le retard sur le premier record qui dépasse la cible, et celui sur le dernier record qui reste en dessous.

## Méthode B : benchmark par benchmark (contrôle)

Pour chaque benchmark où la cible a un score :

1. Même calcul qu'en A, sur le score brut du benchmark.
2. Trois cas particuliers :
   - **cible sous la plus vieille version d'Opus mesurée** : le retard est *au moins* l'écart avec cette version (censure à gauche) ;
   - **cible au-dessus de toutes les versions d'Opus** : le retard est *au plus* l'écart avec la plus récente ;
   - **moins de deux versions d'Opus mesurées** : benchmark écarté.
3. Benchmarks écartés d'office : ceux où la cible a déjà comblé plus de 92 % de la marge entre le score du hasard et le plafond du benchmark. Près du plafond, quelques dixièmes de point valent des mois et le bruit domine.
4. On signale comme « imprécis » les croisements encadrés par deux versions d'Opus séparées de plus de 6 mois (par exemple Claude 3 Opus → Opus 4.5 sur SimpleQA, faute de mesure intermédiaire).
5. Agrégation : médiane des retards, intervalle à 90 % par bootstrap sur les benchmarks. La médiane tolère les valeurs censurées tant qu'elles tombent du bon côté, ce qu'on vérifie en publiant aussi la médiane des seuls croisements interpolés et bien encadrés.

Si la version finale de la cible n'a pas été mesurée sur un benchmark, on prend la preview, avec sa propre date de sortie. Le rapport donne aussi la médiane sans ce repli.

## Cible en avance

Le protocole mesure un retard, pas une avance. Le calcul s'arrête avec une erreur dans deux cas :

- aucune version de la référence n'atteint l'ECI de la cible ;
- la référence n'atteint ce niveau qu'après la sortie de la cible (le retard serait négatif).

Pour mesurer une avance, on inverse les rôles : la référence devient la cible.

## Référence trop récente

Un retard en mois se lit sur une lignée qui a une histoire : il faut au moins une version de la référence sous le niveau de la cible pour dater le croisement. Si tous les modèles de la référence sont au-dessus de la cible *et* sortis après elle (par exemple GPT-6 Luna comparé au seul GPT-6.2 Astra), le croisement ne peut pas être daté. Le calcul s'arrête alors avec un message qui demande d'ajouter les versions précédentes de la lignée. Ce cas n'est pas une avance.

Dans la méthode B, un benchmark dans cette situation est écarté : la borne « au moins X mois » y serait négative et ne dirait rien.

## Pourquoi deux méthodes

L'ECI résume beaucoup de benchmarks en un seul nombre, mais il dépend du modèle statistique d'Epoch. La méthode B est plus brute et montre où se trouve l'écart : connaissances factuelles, maths, code, agents. Si les deux convergent, le résultat tient.

## Limites connues

- **Le retard dépend du rythme de la référence.** Opus a progressé lentement de 4.6 à 4.7 (+1,2 ECI en 2,5 mois), puis vite. Un même écart de niveau vaut plus ou moins de mois selon l'endroit où il tombe sur la courbe.
- **L'interpolation suppose une progression continue entre deux sorties.** En réalité le niveau monte par paliers. Les bornes « premier record au-dessus / dernier en dessous » donnent l'écart en versions réelles.
- **Couverture inégale.** Mistral Large 4 n'est mesuré que sur une quinzaine de benchmarks, Opus sur davantage. Les benchmarks agentiques (Terminal Bench, SWE-bench, OSWorld) manquent souvent pour la cible.
- **Epoch peut réviser ses données.** L'historique (`reports/history.csv`) permet de voir si une révision change la réponse.

## Changer de cible ou de référence

Tout passe par `config.toml` ou la ligne de commande :

```sh
uv run benchlag --target "Kimi K3.1 Pro" --reference "^GPT-" --reference-label GPT --out reports/kimi_vs_gpt
```

Les noms de modèles sont ceux de la colonne `Model` de `eci_scores.csv`.
