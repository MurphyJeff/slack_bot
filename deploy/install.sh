#!/bin/bash
#
# Installation script for CAEP Group Bot on Debian 12 (Bookworm) x86_64.
# Run as root or with sudo. Adapt paths as needed.
#
# Usage: sudo bash deploy/install.sh
#
set -euo pipefail

APP_NAME="group_bot"
APP_DIR="/opt/group_bot"
CONFIG_DIR="/etc/group_bot"
DATA_DIR="/var/lib/group_bot"
SERVICE_USER="groupbot"
SERVICE_GROUP="groupbot"
SERVICE_FILE="deploy/group_caepbot.service"

echo "=== CAEP Group Bot — Installation ==="

# --- 1. System user ---
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "Creating system user: $SERVICE_USER"
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
else
    echo "User $SERVICE_USER already exists."
fi

# --- 2. Directories ---
echo "Creating directories..."
mkdir -p "$APP_DIR" "$CONFIG_DIR" "$DATA_DIR"

# --- 3. Copy application files ---
echo "Copying application files to $APP_DIR..."
rsync -a --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
    --exclude='*.sqlite3' --exclude='.env' --exclude='config.yaml' \
    "$(pwd)/" "$APP_DIR/"

# --- 4. Virtual environment ---
echo "Setting up Python virtual environment..."
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -e "$APP_DIR"

# --- 5. Config file ---
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    echo "Copying example config to $CONFIG_DIR/config.yaml"
    cp "$APP_DIR/config.example.yaml" "$CONFIG_DIR/config.yaml"
    echo ">>> EDIT $CONFIG_DIR/config.yaml with your real group/user IDs <<<"
else
    echo "Config file already exists at $CONFIG_DIR/config.yaml (skipping)"
fi

# --- 6. Secrets file ---
SECRETS_FILE="$CONFIG_DIR/secrets.env"
if [ ! -f "$SECRETS_FILE" ]; then
    echo "Creating secrets template at $SECRETS_FILE"
    cat > "$SECRETS_FILE" <<EOF
# Fill with your real Slack tokens. NEVER commit this file.
SLACK_APP_TOKEN=
SLACK_BOT_TOKEN=
SLACK_SIGNING_SECRET=
EOF
    echo ">>> EDIT $SECRETS_FILE with your real Slack tokens <<<"
else
    echo "Secrets file already exists at $SECRETS_FILE (skipping)"
fi

# --- 7. Permissions ---
echo "Setting permissions..."
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$DATA_DIR"
chown root:root "$CONFIG_DIR" "$SECRETS_FILE"
chmod 0640 "$CONFIG_DIR/config.yaml"
chmod 0600 "$SECRETS_FILE"
chmod -R go-w "$APP_DIR"

# --- 8. Systemd service ---
echo "Installing systemd service..."
cp "$APP_DIR/$SERVICE_FILE" /etc/systemd/system/

echo "Verifying service file..."
systemd-analyze verify /etc/systemd/system/group_caepbot.service

systemctl daemon-reload

echo ""
echo "=== Installation complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit $CONFIG_DIR/config.yaml — set your real group/user IDs"
echo "  2. Edit $SECRETS_FILE — set your Slack tokens"
echo "  3. Start the service:  sudo systemctl enable --now group_caepbot"
echo "  4. Check logs:         journalctl -u group_caepbot -f"
echo ""
