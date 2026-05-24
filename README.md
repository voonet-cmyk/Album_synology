# 📸 Album du jour — Synology Photos

> Script Python qui crée automatiquement chaque matin un album photo sur ton NAS Synology,
> en piochant des souvenirs selon le thème du jour : anniversaires de la même date,
> photos de saison, ou sélection aléatoire dans toute la bibliothèque.

---

## 🗓️ Comment ça marche au quotidien

Chaque matin à l'heure que tu as choisie, le NAS lance le script tout seul. Le script
se connecte à Synology Photos, sélectionne une trentaine de photos selon le thème du
jour (un jour c'est des souvenirs d'il y a 1, 2, 5 ou 10 ans exactement ; un autre jour
des photos du même mois toutes années confondues ; un autre jour une pioche aléatoire
dans toute la bibliothèque), puis met à jour un album existant en remplaçant les photos
de la veille par celles du jour. L'album reste au même endroit avec les mêmes personnes
invitées — seules les photos changent. Il n'y a rien à faire de ta part : tu ouvres
Synology Photos le matin et les nouvelles photos sont là.

---

## ✅ Prérequis

| Ce qu'il faut | Pourquoi |
|---|---|
| **NAS Synology avec DSM 7.2 ou plus récent** | DSM est le système d'exploitation du NAS. La version 7.2 apporte l'API Photos dont le script a besoin. |
| **Application Synology Photos installée** | C'est l'application de gestion de photos sur le NAS, disponible gratuitement dans le Centre de paquets. |
| **Python 3.9 ou plus** | Python est le langage dans lequel le script est écrit. Tu l'installes depuis le Centre de paquets du NAS (paquet nommé "Python 3"). |
| **Deux comptes utilisateurs sur le NAS** | `your_user` : ton compte personnel pour SSH et l'installation. `script_user` : compte dédié que le script utilise pour accéder à l'API Photos. Le compte `script_user` doit avoir accès à l'espace partagé Synology Photos. |

---

## 🖥️ Installation sur le NAS Synology

Cette section détaille chaque étape depuis ton PC Windows jusqu'au premier lancement automatique.

---

### Étape A — Activer SSH dans DSM

SSH est un système qui te permet de donner des commandes au NAS depuis ton PC, comme si tu avais un clavier branché dessus.

**Dans DSM :**

1. Clique sur **Panneau de configuration** (icône de boîte à outils sur le bureau DSM)
2. Dans la liste de gauche, clique sur **Terminal et SNMP**

   > 📺 *Tu vois une page avec deux onglets : "Terminal" et "SNMP". Tu es sur le bon écran.*

3. Coche la case **Activer le service SSH**
4. Le port peut rester sur **22** (c'est la valeur standard)
5. Clique sur **Appliquer**

   > 📺 *Un message de confirmation s'affiche brièvement en bas de l'écran. SSH est maintenant actif.*

---

### Étape B — Installer PuTTY et se connecter en SSH depuis Windows

**Télécharge et installe PuTTY** (client SSH pour Windows) :
[https://www.putty.org](https://www.putty.org) → bouton "Download PuTTY"

> PowerShell dispose d'un client SSH intégré, mais il peut rencontrer des problèmes
> de compatibilité d'algorithmes avec certains NAS Synology. PuTTY est plus fiable.

**Ouvre PuTTY** et configure la connexion :
- Host Name : `192.168.X.X` (remplace par l'IP de ton NAS)
- Port : `22`
- Connection type : `SSH`
- Clique sur **Open**

> 📺 *La première fois, PuTTY affiche une alerte de sécurité sur la clé du serveur.
> Clique sur "Accept". Une fenêtre noire s'ouvre et demande ton identifiant.*

Entre ton nom d'utilisateur (`your_user`) puis ton mot de passe
(les caractères n'apparaissent pas à l'écran, c'est normal).

Tu es connecté quand tu vois une ligne qui ressemble à :
```
your_user@DiskStation:~$
```

> Tu trouves l'IP du NAS dans DSM → Panneau de configuration → Réseau → Général.

---

### Étape C — Copier le projet sur le NAS

> **Note importante sur les chemins :** L'interface DSM File Station affiche des chemins
> raccourcis, différents des chemins réels utilisés en SSH. La correspondance est :
>
> | Ce que tu vois dans File Station | Ce que tu tapes en SSH |
> |---|---|
> | `home/download/MonDossier` | `/volume1/homes/YOUR_USER/download/MonDossier` |
> | `home/Job/MonDossier` | `/volume1/homes/YOUR_USER/Job/MonDossier` |
>
> En pratique : remplace `home/` par `/volume1/homes/YOUR_USER/` pour obtenir le chemin SSH.

**Sur ton PC Windows**, ouvre une fenêtre PowerShell (touche Windows → "PowerShell") et tape :

```powershell
scp -r "C:\Users\YOUR_USERNAME\Claude\Album" your_user@192.168.X.X:/volume1/homes/YOUR_USER/download/AlbumPhotoAuto
```

Adapte `C:\Users\YOUR_USERNAME\Claude\Album` au dossier où se trouve le projet sur ton PC,
et `192.168.X.X` à l'adresse IP de ton NAS.

> 📺 *PowerShell affiche les fichiers au fur et à mesure de la copie, avec leur taille.
> Quand c'est terminé, la commande rend la main sans message d'erreur.*

---

### Étape D — Lancer le script d'installation

**Dans la fenêtre PuTTY connectée au NAS** (celle qui affiche `your_user@DiskStation:~$`) :

```bash
cd /volume1/homes/YOUR_USER/download/AlbumPhotoAuto
bash scripts/install_on_dsm.sh
```

> 📺 *Le script affiche sa progression avec des coches vertes (✓). Il crée le répertoire
> `/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/`, installe Python dans un espace isolé, et
> copie tous les fichiers nécessaires. À la fin, il affiche un récapitulatif des
> commandes à utiliser.*

En cas de répertoire d'installation différent, tu peux le préciser :

```bash
bash scripts/install_on_dsm.sh /volume2/mes-scripts/album
```

---

### Étape E — Remplir le fichier de configuration

Le script d'installation a créé un fichier `config.yml` vierge à remplir.
Ouvre-le avec l'éditeur de texte intégré :

```bash
nano /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml

> (Dans File Station, ce dossier est visible sous `home/Job/AlbumPhotoAuto/`)
```

> 📺 *L'éditeur nano s'ouvre dans le terminal. Les touches fléchées déplacent le curseur.
> Quand tu as fini, appuie sur `Ctrl+X`, puis `O` (oui pour sauvegarder), puis `Entrée`.*

> **Note sur les comptes :** Il y a deux comptes distincts sur le NAS.
> - `your_user` : ton compte personnel, utilisé pour la connexion SSH et l'installation.
> - `script_user` : compte dédié utilisé par le script pour accéder à l'API Synology Photos.
> Ces deux choses sont indépendantes. Ici tu renseignes les identifiants du compte `script_user`.

Remplis **au minimum** ces quatre lignes :

```yaml
synology:
  host: "http://192.168.X.X"      # ← l'adresse IP de ton NAS
  port: 5000
  username: "script_user"          # ← le compte dédié script (≠ ton compte SSH your_user)
  password: "ton_mot_de_passe"     # ← mot de passe du compte script_user
```

Voir la section **Configuration** plus bas pour le détail de tous les réglages.

---

### Étape F — Tester sans rien modifier

```bash
/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/.venv/bin/python \
  /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/main.py \
  --config /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml \
  --dry-run --debug
```

> 📺 *Le terminal affiche chaque action que le script AURAIT faite, sans toucher au NAS.
> La dernière ligne doit afficher "SIMULATION TERMINEE" avec le nombre de photos
> sélectionnées. Si tu vois "ERREUR", lis le message : il dit exactement ce qui
> ne va pas (mauvais mot de passe, IP incorrecte, etc.).*

---

### Étape G — Premier vrai lancement

Quand le test de simulation s'est bien passé, lance pour de vrai :

```bash
/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/.venv/bin/python \
  /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/main.py \
  --config /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml \
  --debug
```

Les albums apparaissent dans Synology Photos (section Albums). Va les partager
manuellement avec les personnes de ton choix (voir Étape H).

---

### Étape H — Configurer le partage des albums (une seule fois)

1. Ouvre **Synology Photos** dans ton navigateur
2. Va dans la section **Albums** dans le menu de gauche

   > 📺 *Tu vois les albums créés : "Album du jour — Anniversaires", "Album du jour — Saison", "Album du jour — Aleatoire". Il peut en manquer si le thème du jour n'a pas encore tourné — c'est normal.*

3. Pour **chaque album**, clique dessus avec le bouton droit → **Partager**
   (ou clique sur les trois points `⋯` qui apparaissent au survol)
4. Dans la fenêtre de partage :
   - Clique sur **Inviter des utilisateurs**
   - Tape le nom du compte à inviter, sélectionne-le
   - Règle le rôle sur **Visionneur**
   - Clique sur **Enregistrer**

Le script ne touche jamais au partage. Les invités restent d'un jour à l'autre.

---

### Étape I — Configurer la tâche planifiée dans DSM

C'est ce qui fait que le script se lance tout seul chaque matin.

1. Dans DSM, clique sur **Panneau de configuration**
2. Clique sur **Planificateur de tâches**

   > 📺 *Une fenêtre s'ouvre avec la liste des tâches (elle peut être vide). La barre
   > d'outils en haut propose : Créer / Modifier / Supprimer / Exécuter.*

3. Clique sur **Créer → Tâche planifiée → Script défini par l'utilisateur**

   > 📺 *Une fenêtre à trois onglets s'ouvre : Général / Planifier / Paramètres de la tâche.*

4. **Onglet Général** :
   - Nom de la tâche : `Album du jour`
   - Utilisateur : sélectionne le compte `your_user`
   - Laisse "Activée" cochée

5. **Onglet Planifier** :
   - Exécuter : `Quotidien`
   - Heure : `06:00` (ou l'heure de ton choix)
   - Répéter : décoché (une seule fois par jour suffit)

6. **Onglet Paramètres de la tâche** :
   - Dans le champ **Exécuter la commande**, colle exactement :

   ```
   /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/.venv/bin/python /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/main.py --config /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml
   ```

   > 📺 *C'est une seule ligne, sans retour à la ligne. Si tu as installé dans un
   > répertoire différent, adapte les chemins en conséquence.*

   - Dans **Envoyer les informations d'exécution par e-mail**, tu peux entrer ton adresse
     si tu veux être notifié en cas d'erreur.

7. Clique sur **OK**

---

### Étape J — Tester avec "Exécuter maintenant"

Pour vérifier que la tâche planifiée fonctionne correctement sans attendre demain matin :

1. Dans le **Planificateur de tâches**, clique sur la tâche `Album du jour` pour la sélectionner
2. Clique sur **Exécuter** dans la barre d'outils

   > 📺 *Une boîte de dialogue demande confirmation. Clique sur Oui. La tâche se lance
   > en arrière-plan — aucune fenêtre ne s'ouvre, c'est normal.*

3. Attends 30 secondes à 2 minutes selon la taille de ta bibliothèque
4. Va dans Synology Photos → Albums : les photos de l'album ont changé

Pour voir le résultat détaillé de l'exécution :
- Dans le Planificateur de tâches, clique sur la tâche → **Résultats**
- La colonne "Informations" indique si la tâche a réussi ou échoué

---

### Étape K — Où trouver les logs en cas de problème

Le script écrit un journal détaillé à cet emplacement :

```
/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/logs/album.log
```

**Pour le lire depuis SSH :**
```bash
tail -50 /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/logs/album.log
```
(affiche les 50 dernières lignes — celles du dernier lancement)

**Pour le lire depuis DSM :**
Ouvre **File Station**, navigue vers `/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/logs/`,
double-clique sur `album.log`.

Une ligne d'erreur ressemble à :
```
2026-05-15 06:00:12 | ERROR    | Erreur d'authentification : ...
```
Le texte après les deux-points explique la cause.

---

## ⚙️ Configuration — que mettre dans `config.yml`

Voici le fichier expliqué ligne par ligne. Les lignes qui commencent par `#` sont des commentaires ignorés par le script.

```yaml
synology:
  host: "http://192.168.X.X"      # L'adresse IP de ton NAS sur le réseau local
  port: 5000                      # 5000 = connexion standard, 5001 = connexion chiffrée (HTTPS)
  username: "script_user"         # Le compte dédié qui se connecte pour créer les albums (≠ ton compte SSH your_user)
  password: "mon_mot_de_passe"    # Son mot de passe — ne partage JAMAIS ce fichier

album:
  name_prefix: "Album du jour"    # Le début du nom de chaque album (suivi du thème)
  photo_count: 30                 # Nombre de photos dans chaque album

cache:
  max_age_hours: 24               # Le script reliste toutes les photos toutes les 24h
  force_refresh: false            # Passe à true pour forcer une relecture complète au prochain lancement

themes:
  rotation: "anniversary,season,random"    # Ordre de rotation des thèmes
  anniversary_years_back: "1,2,3,5,10"    # Années en arrière pour le thème anniversaire
  # exclude_paths: "19*,VHS*,Archives"     # Dossiers à ne jamais inclure (les * sont des jokers)
  no_repeat_days_anniversary: 30           # Une photo d'anniversaire ne revient pas avant 30 jours
  no_repeat_days_season: 30               # Idem pour le thème saison
  no_repeat_days_random: 30               # Idem pour le thème aléatoire (0 = désactivé)

logs:
  retention_days: 30              # Nombre de jours de logs conservés
  level: "INFO"                   # INFO = normal | DEBUG = très détaillé (pour déboguer)
```

### Les thèmes en détail

| Nom | Ce que ça donne |
|---|---|
| `anniversary` | Photos prises autour de la même date du calendrier (± quelques jours) dans les années précédentes. Ex : le 15 mai, il cherche des photos du 15 mai 2024, 2022, 2020, 2015… |
| `season` | Photos prises pendant le même mois que aujourd'hui, toutes années confondues. En mai → photos de tous les mois de mai. |
| `random` | Tirage au sort dans toute la bibliothèque. |

La valeur `rotation: "anniversary,season,random"` signifie que les thèmes tournent dans cet ordre, jour après jour. Avec 3 thèmes : jour 1 → anniversaire, jour 2 → saison, jour 3 → aléatoire, jour 4 → anniversaire, etc.

### Éviter les répétitions de photos

Par défaut, une photo qui a déjà été montrée dans un album ne réapparaît pas pendant **30 jours** pour ce même thème. Cette fenêtre est configurable indépendamment pour chaque thème :

```yaml
themes:
  no_repeat_days_anniversary: 30   # jours de "quarantaine" pour le thème anniversaire
  no_repeat_days_season: 30        # idem pour saison
  no_repeat_days_random: 30        # idem pour aléatoire
```

**Exemples de réglage :**

| Cas | Réglage |
|---|---|
| Bibliothèque de moins de 500 photos → risque de manque | Réduire à `14` ou `7` |
| Grande bibliothèque, pas de répétition pendant 2 mois | Mettre à `60` |
| Désactiver complètement pour un thème | Mettre à `0` |

**Ce qui se passe si toutes les photos sont en quarantaine** (bibliothèque trop petite) : le script ignore la contrainte de non-répétition pour ce lancement et choisit quand même des photos. Un avertissement est écrit dans les logs.

L'historique est stocké dans `cache/history.json`. Il est purgé automatiquement — seules les entrées dans la plus grande fenêtre configurée sont conservées.

---

### Exclure des dossiers

Si tu as des dossiers que tu ne veux jamais voir dans les albums (numérisations VHS, archives de travail, etc.) :

```yaml
  exclude_paths: "VHS*,19*,Travail,Famille/Archives"
```

- `VHS*` → tous les dossiers dont le nom commence par `VHS`
- `19*` → tous les dossiers dont le nom commence par `19` (ex : `1994`, `1998`)
- `Travail` → exactement le dossier nommé `Travail`
- `Famille/Archives` → le sous-dossier `Archives` à l'intérieur de `Famille`

Après avoir modifié cette liste, relance avec `--rebuild-index` pour reconstruire la liste des photos :

```bash
/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/.venv/bin/python \
  /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/main.py \
  --config /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml \
  --rebuild-index --dry-run
```

---

## 🔄 Modifier la fréquence ou les thèmes

### Changer l'heure de lancement

Dans DSM → **Planificateur de tâches**, double-clique sur la tâche `Album du jour`, onglet **Planifier**, change l'heure.

### Activer ou désactiver un thème

Dans `config.yml`, modifie la ligne `rotation`. Par exemple pour n'avoir que des albums aléatoires :

```yaml
  rotation: "random"
```

Pour alterner uniquement anniversaires et saison :

```yaml
  rotation: "anniversary,season"
```

### Forcer un thème manuellement (pour tester)

```bash
PYTHON=/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/.venv/bin/python
MAIN=/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/main.py
CONFIG=/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml

$PYTHON $MAIN --config $CONFIG --theme random
$PYTHON $MAIN --config $CONFIG --theme anniversary
$PYTHON $MAIN --config $CONFIG --theme season
```

---

## 🔍 Dépannage — si l'album n'est pas mis à jour le matin

### 1. Regarder les logs

```bash
tail -50 /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/logs/album.log
```

### 2. Relancer manuellement en mode verbeux

```bash
/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/.venv/bin/python \
  /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/main.py \
  --config /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml \
  --debug
```

Un message `ERROR` ou `WARNING` indique où ça coince.

### 3. Tester la connexion sans rien modifier

```bash
/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/.venv/bin/python \
  /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/main.py \
  --config /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml \
  --dry-run --debug
```

### 4. Reconstruire la liste des photos

Si le script dit que l'index est vide ou qu'aucune photo n'est trouvée :

```bash
/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/.venv/bin/python \
  /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/main.py \
  --config /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml \
  --rebuild-index --debug
```

### 5. Problèmes courants

| Symptôme | Cause probable | Solution |
|---|---|---|
| `Erreur d'authentification` | Mauvais identifiant ou mot de passe | Vérifie `username` et `password` dans `config.yml` |
| `L'index est vide` | Le compte n'a pas accès à l'espace partagé | Dans Synology Photos → Paramètres → Espace partagé → Autorisations, ajoute le compte `script_user` |
| `Erreur de configuration` | `config.yml` mal rempli ou absent | Vérifie que le fichier existe et que toutes les sections sont présentes |
| Les albums ne sont plus partagés | L'album a été supprimé et recréé manuellement | Reconfigurer le partage dans Synology Photos (voir Étape H) |
| Aucune photo pour le thème anniversaire | Pas de photos à cette date dans les années passées | Normal : le script bascule automatiquement sur le thème aléatoire |
| Des photos se répètent malgré la non-répétition | Bibliothèque trop petite pour la fenêtre configurée | Réduire `no_repeat_days_*` dans `config.yml`, ou vérifier le log (`Toutes les photos du pool sont dans l'historique`) |
| La tâche planifiée ne se lance pas | Mauvais utilisateur sélectionné | Vérifie que l'utilisateur dans le Planificateur a les droits sur le répertoire du script |

---

## ⚠️ Limites connues

- **Le partage des albums doit être configuré à la main.** L'API Synology Photos ne permet pas d'ajouter des utilisateurs invités via un script — cette action doit être faite une fois dans l'interface web.

- **Les photos sans date de prise de vue sont ignorées par le thème anniversaire.** Les fichiers sans métadonnées n'apparaissent que dans le thème aléatoire.

- **Le thème anniversaire peut ne rien trouver.** Si aucune photo n'a été prise autour de la date courante dans les années passées, le script bascule automatiquement sur le thème aléatoire.

- **Un seul album par thème.** Si le script tourne deux fois le même jour, il remplace simplement les photos — pas de doublon.

- **L'index des photos est mis en cache 24h.** Si tu ajoutes de nouvelles photos sur le NAS, relance avec `--rebuild-index` pour qu'elles soient prises en compte immédiatement.

---

## 📋 POUR L'UTILISATEUR

### Check-list de validation — à cocher dans l'ordre

```
INSTALLATION
  [ ] A. SSH activé dans DSM (Panneau de configuration → Terminal et SNMP)
  [ ] B. PuTTY installé, connexion SSH testée avec succès
           PuTTY → Host: 192.168.X.X, Port: 22 → connecté en your_user
  [ ] C. Projet copié sur le NAS avec scp (depuis PowerShell sur le PC)
           scp -r "C:\...\Album" your_user@NAS_IP:/volume1/homes/YOUR_USER/download/AlbumPhotoAuto
  [ ] D. Script d'installation lancé sans erreur rouge (depuis PuTTY sur le NAS)
           cd /volume1/homes/YOUR_USER/download/AlbumPhotoAuto
           bash scripts/install_on_dsm.sh
  [ ] E. config.yml rempli avec l'IP, le compte et le mot de passe du NAS

TEST
  [ ] F. Simulation OK (aucune erreur, photos sélectionnées)
           ... main.py --dry-run --debug
  [ ] G. Premier vrai lancement OK (albums visibles dans Synology Photos)
           ... main.py --debug
  [ ] H. Albums partagés manuellement dans Synology Photos
           (Albums → ⋯ → Partager → Inviter → Visionneur)
           Album du jour — Anniversaires  [ ]
           Album du jour — Saison         [ ]
           Album du jour — Aleatoire      [ ]

AUTOMATISATION
  [ ] I. Tâche planifiée créée dans DSM (Planificateur de tâches)
           Utilisateur : your_user
           Heure       : 06:00
           Commande    : /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/.venv/bin/python
                         /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/main.py
                         --config /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml
  [ ] J. "Exécuter maintenant" testé → album mis à jour dans Synology Photos
  [ ] K. Logs vérifiés (aucune ligne ERROR)
           /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/logs/album.log
```

```
┌──────────────────────────────────────────────────────────────┐
│                   RÉSUMÉ EN UNE PAGE                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  FICHIER À NE JAMAIS PARTAGER : config.yml                   │
│  (contient ton mot de passe NAS)                             │
│                                                              │
│  CE QUI TOURNE TOUT SEUL (ne touche à rien) :               │
│  → Le script se lance chaque matin à 06:00                   │
│  → Il remplace les photos dans les albums existants          │
│  → Si un album n'existe pas encore, il le crée               │
│                                                              │
│  CE QUI NE SE FAIT QU'UNE SEULE FOIS (à la main) :          │
│  → Configurer qui voit chaque album dans Synology Photos     │
│    (Albums → ⋯ → Partager → Inviter → Visionneur)           │
│                                                              │
│  SI QUELQUE CHOSE NE MARCHE PAS :                            │
│  1. Lire : logs/album.log (dernières lignes)                 │
│  2. SSH sur le NAS et relancer avec --debug                  │
│  3. Résultats de la tâche dans le Planificateur DSM          │
│                                                              │
│  TESTER SANS RIEN MODIFIER :                                 │
│  → main.py --dry-run --debug                                 │
│                                                              │
│  FORCER UN THÈME :                                           │
│  → main.py --theme random                                    │
│  → main.py --theme anniversary                               │
│  → main.py --theme season                                    │
│                                                              │
│  ALBUMS (noms dans Synology Photos) :                        │
│  → "Album du jour — Anniversaires"                           │
│  → "Album du jour — Saison"                                  │
│  → "Album du jour — Aleatoire"                               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```
