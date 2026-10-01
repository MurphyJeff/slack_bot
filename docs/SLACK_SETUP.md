# Slack App Setup — CAEP Group Bot

## 1. Créer l'application Slack

> Si l'app "CAEP Bot" est déjà créée, passer à l'étape 2.

1. Aller sur https://api.slack.com/apps → **Create New App** → **From scratch**
2. Nommer l'app: `CAEP Bot`
3. Sélectionner le workspace de l'association

## 2. Activer Socket Mode

1. **Settings** → **Socket Mode** → toggle ON
2. Cliquer **Generate an App-Level Token**
3. Nom: `group-bot-socket`
4. Scope: `connections:write`
5. Copier le token `xapp-...` → mettre dans `.env` comme `SLACK_APP_TOKEN`

## 3. Configurer les scopes (OAuth & Permissions)

Aller dans **OAuth & Permissions** → **Bot Token Scopes** et ajouter:

| Scope | Pourquoi |
|---|---|
| `chat:write` | Publier les notifications dans les fils |
| `channels:history` | Lire les messages des canaux publics |
| `groups:history` | Lire les messages des canaux privés |
| `users:read` | Valider les user IDs au démarrage (optionnel) |

> **À vérifier dans les sources officielles Slack** : la liste exacte des
> scopes peut évoluer. Vérifier sur https://api.slack.com/scopes.

Ne **PAS** ajouter de scopes administratifs (`admin.*`, `client.*`).

## 4. Activer les événements

Aller dans **Event Subscriptions** → toggle ON.

**Subscribe to bot events** — ajouter:

- `message.channels` (messages dans les canaux publics)
- `message.groups` (messages dans les canaux privés)
- `message.im` (optionnel: messages privés)
- `message.mpim` (optionnel: messages de groupe privés)

> En Socket Mode, l'URL de requête n'est pas nécessaire. Slack pousse
> les événements via la connexion WebSocket.

## 5. Installer l'app dans le workspace

1. **OAuth & Permissions** → **Install to Workspace**
2. Autoriser les permissions demandées
3. Copier le **Bot User OAuth Token** `xoxb-...` → mettre dans `.env` comme `SLACK_BOT_TOKEN`

## 6. Récupérer le Signing Secret

1. **Basic Information** → **App Credentials**
2. Copier le **Signing Secret** → mettre dans `.env` comme `SLACK_SIGNING_SECRET`

## 7. Fichier `.env` local (développement)

```bash
cp .env.example .env
# Éditer .env avec les 3 valeurs ci-dessus
```

> **JAMAIS commiter `.env`** — le repo est public !

## 8. Ajouter le bot aux canaux

### Canal public

1. Ouvrir le canal dans Slack
2. Taper `@CAEP Bot` ou aller dans les paramètres → **Add apps**
3. Sélectionner le bot

### Canal privé

1. Un membre autorisé tape `/invite @CAEP Bot`
2. Le bot ne peut pas rejoindre un canal privé sans invitation explicite

## 9. Checklist de validation

- [ ] Socket Mode activé, App Token généré
- [ ] Scopes configurés (chat:write, channels:history, groups:history)
- [ ] Événements activés (message.channels, message.groups)
- [ ] App installée dans le workspace
- [ ] Bot Token et Signing Secret récupérés
- [ ] `.env` configuré localement (développement)
- [ ] Bot ajouté à un canal de test public
- [ ] Message de test avec `@com` envoyé → notification reçue dans le fil
- [ ] `@ici` ou `@here` envoyé → aucune notification du bot
- [ ] Bot ajouté à un canal privé (via invitation) → test fonctionnel
- [ ] Redémarrage du service → pas de double notification

## 10. Limites et vérifications à effectuer

- Toute information concernant les forfaits Slack, les limites d'événements
  ou la tarification doit être vérifiée dans la documentation officielle:
  https://api.slack.com/apis/connections/socket-mode
- Le Socket Mode nécessite que l'app ait au moins une connexion active.
  Si le bot est arrêté, les événements ne sont pas reçus (pas de file d'attente).
- Les canaux privés nécessitent une invitation explicite du bot.
