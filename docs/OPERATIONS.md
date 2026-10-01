# Opérations — CAEP Group Bot

## Rotation des tokens Slack

Les tokens Slack peuvent expirer ou être révoqués. Procédure de rotation:

### 1. Générer de nouveaux tokens

1. https://api.slack.com/apps → sélectionner l'app
2. **Settings** → **Socket Mode** → regenerate App Token
3. **OAuth & Permissions** → reinstall app → new Bot Token
4. **Basic Information** → rotate Signing Secret

### 2. Mettre à jour le serveur

```bash
sudo nano /etc/group_bot/secrets.env
# Remplacer les 3 valeurs
sudo systemctl restart group_caepbot
journalctl -u group_caepbot -f
```

### 3. En développement

```bash
nano .env
# Remplacer les valeurs
# Redémarrer le bot
```

> **Important**: l'ancien Bot Token est immédiatement invalidé après
> réinstallation. Le bot sera hors ligne jusqu'à la mise à jour.

## Procédure de dépannage

### Logs structurés (JSON)

Les logs sont au format JSON via structlog. Exemples de requêtes journald:

```bash
# Toutes les erreurs
journalctl -u group_caepbot | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line.split(']', 2)[-1].strip())
        if d.get('level') == 'error':
            print(d)
    except: pass
"

# Notifications envoyées
journalctl -u group_caepbot | grep 'notification_posted'

# Déduplication
journalctl -u group_caepbot | grep 'already_notified'

# Alias détectés
journalctl -u group_caepbot | grep 'aliases_detected'
```

### Inspection de la base SQLite

```bash
# Nombre total d'enregistrements
sudo sqlite3 /var/lib/group_bot/state.sqlite3 \
    "SELECT COUNT(*) FROM notifications_sent;"

# Notifications récentes (IDs tronqués pour sécurité)
sudo sqlite3 /var/lib/group_bot/state.sqlite3 \
    "SELECT substr(channel_id,1,4)||'****', substr(message_ts,1,7)||'***', \
    substr(user_id,1,4)||'****', created_at FROM notifications_sent \
    ORDER BY created_at DESC LIMIT 20;"

# Nettoyage manuel
sudo sqlite3 /var/lib/group_bot/state.sqlite3 \
    "DELETE FROM notifications_sent WHERE created_at < datetime('now', '-90 days');"

# Réinitialiser complètement (attention !)
sudo systemctl stop group_caepbot
sudo rm /var/lib/group_bot/state.sqlite3
sudo systemctl start group_caepbot
```

### Vérifier la configuration sans démarrer le bot

```bash
# Tester le chargement de la config
SLACK_APP_TOKEN=test SLACK_BOT_TOKEN=test SLACK_SIGNING_SECRET=test \
    python3 -c "
from group_bot.config import load_config
c = load_config('/etc/group_bot/config.yaml')
print('Groups:', list(c.groups.keys()))
for alias, entries in c.groups.items():
    print(f'  {alias}: {len(entries)} user(s)')
print('Template:', c.notifications.message_template)
print('Exclude author:', c.notifications.exclude_author)
"
```

## Politique de rétention

- **Déduplication SQLite**: nettoyage auto au démarrage, `dedup_days: 90` par défaut
- **Logs journald**: configurés par systemd (`journalctl --vacuum-time=30d` pour 30 jours)
- **Aucune donnée de message stockée**: seuls `channel_id`, `message_ts`, `user_id` sont persistés

## Limites connues

1. **Instance unique**: SQLite ne supporte pas le multi-instance.
   Pour plusieurs instances, migrer vers PostgreSQL.
2. **Pas d'atomicité Slack ↔ SQLite**: si Slack réussit mais DB échoue,
   le bot peut renotifier au prochain événement redélivré. C'est acceptable
   car Slack redélivre les événements non acquittés.
3. **Socket Mode**: si le bot est arrêté, les événements sont perdus
   (pas de file d'attente côté Slack). Utiliser `Restart=on-failure`.
4. **Canaux privés**: le bot ne reçoit les événements que s'il est
   explicitement invité (`/invite @CAEP Bot`).
5. **Validation des user_ids**: les IDs sont validés par format (regex)
   au chargement de la config. La validation contre l'API Slack
   nécessite le scope `users:read` et n'est pas activée par défaut.

## Décisions restant à prendre

- Texte exact du template de notification (actuel: `cc {mentions}`)
- Durée de rétention SQLite (actuel: 90 jours)
- Activation de la validation des user_ids via l'API Slack au démarrage
- Implémentation de slash commands pour éditer les groupes depuis Slack
- Gestion des messages modifiés (re-détection des alias après édition)
