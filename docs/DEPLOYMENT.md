# Déploiement Debian 12 — CAEP Group Bot

## Prérequis

- Debian 12 (Bookworm) x86_64
- Python 3.11+ (`apt install python3 python3-venv`)
- Accès root ou sudo
- Tokens Slack configurés (voir [SLACK_SETUP.md](./SLACK_SETUP.md))

## Installation automatisée

```bash
# Cloner le dépôt
git clone <repo-url> /tmp/group_bot
cd /tmp/group_bot

# Lancer l'installation
sudo bash deploy/install.sh
```

Le script:
1. Crée un utilisateur système `groupbot` (nologin)
2. Copie les fichiers vers `/opt/group_bot`
3. Crée un venv Python et installe les dépendances
4. Crée `/etc/group_bot/config.yaml` et `/etc/group_bot/secrets.env` (templates)
5. Configure les permissions (0600 pour secrets, 0640 pour config)
6. Installe et vérifie le service systemd

## Configuration post-installation

### 1. Éditer la config

```bash
sudo nano /etc/group_bot/config.yaml
```

Remplacer les user IDs d'exemple par les vrais IDs Slack:
```yaml
groups:
  com:
    - user_id: "U_VRAI_ID_1"  # Martine
  bureau:
    - user_id: "U_VRAI_ID_2"  # Martin
```

### 2. Éditer les secrets

```bash
sudo nano /etc/group_bot/secrets.env
```

```bash
SLACK_APP_TOKEN=xapp-1-...
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
```

### 3. Démarrer le service

```bash
sudo systemctl enable --now group_caepbot
```

## Vérification

```bash
# Statut du service
sudo systemctl status group_caepbot

# Logs en temps réel
journalctl -u group_caepbot -f

# Vérifier que le Socket Mode est connecté
journalctl -u group_caepbot | grep "socket_mode_starting"
```

## Chemins importants

| Chemin | Description | Permissions |
|---|---|---|
| `/opt/group_bot` | Application + venv | root:root |
| `/etc/group_bot/config.yaml` | Configuration | root:root 0640 |
| `/etc/group_bot/secrets.env` | Tokens Slack | root:root 0600 |
| `/var/lib/group_bot/state.sqlite3` | Base de déduplication | groupbot:groupbot |

## Mise à jour

```bash
cd /tmp/group_bot
git pull
sudo rsync -a --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
    --exclude='*.sqlite3' --exclude='.env' --exclude='config.yaml' \
    /tmp/group_bot/ /opt/group_bot/
sudo /opt/group_bot/.venv/bin/pip install -e /opt/group_bot
sudo systemctl restart group_caepbot
```

## Sauvegarde de l'état

La base SQLite contient l'historique de déduplication. Sauvegarder:

```bash
sudo cp /var/lib/group_bot/state.sqlite3 /backup/state-$(date +%Y%m%d).sqlite3
```

Restaurer:

```bash
sudo systemctl stop group_caepbot
sudo cp /backup/state-20260101.sqlite3 /var/lib/group_bot/state.sqlite3
sudo chown groupbot:groupbot /var/lib/group_bot/state.sqlite3
sudo systemctl start group_caepbot
```

## Diagnostic

### Le bot ne répond pas

1. Vérifier le statut: `systemctl status group_caepbot`
2. Vérifier les logs: `journalctl -u group_caepbot -n 50`
3. Vérifier que les tokens sont valides (non expirés)
4. Vérifier que le bot est membre du canal
5. Tester avec un message contenant `@com` dans un canal de test

### Doublons de notification

1. Vérifier la base: `sqlite3 /var/lib/group_bot/state.sqlite3 "SELECT COUNT(*) FROM notifications_sent;"`
2. Le nettoyage automatique s'effectue au démarrage (retention.dedup_days)

### Erreur de rate limit Slack

Les logs affichent `rate_limited` — le bot retry automatiquement avec
backoff. Si persistant, vérifier le nombre de canaux surveillés.
