#!/bin/bash
# =============================================================================
# WordPress Vulnerable Setup — runs on first boot
# =============================================================================
# Installs deliberately vulnerable plugins and configures weak settings.
# Idempotent — safe to run on restart.
set -e

# Wait for MariaDB (using PHP mysqli since mysqladmin is not installed)
until php -r "\$c = @new mysqli('${WORDPRESS_DB_HOST}', '${WORDPRESS_DB_USER}', '${WORDPRESS_DB_PASSWORD}'); if(\$c->connect_error) exit(1);" 2>/dev/null; do
    echo "[entrypoint-vuln] Waiting for MariaDB..."
    sleep 2
done
echo "[entrypoint-vuln] MariaDB is ready."

# Run the standard WordPress entrypoint first
docker-entrypoint.sh apache2-foreground &
WP_PID=$!

# Wait for WordPress to become available
echo "[entrypoint-vuln] Waiting for WordPress to initialise..."
for i in $(seq 1 60); do
    if curl -sf http://localhost/wp-login.php >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

# Install WordPress if not already installed
if ! wp core is-installed --path=/var/www/html --allow-root 2>/dev/null; then
    echo "[entrypoint-vuln] Installing WordPress..."
    wp core install \
        --path=/var/www/html \
        --url="http://localhost:8080" \
        --title="CorpSite" \
        --admin_user=admin \
        --admin_password=admin123 \
        --admin_email=admin@psyche.local \
        --allow-root

    # Enable XML-RPC (on by default, but ensure it)
    wp option update xmlrpc_enabled 1 --path=/var/www/html --allow-root 2>/dev/null || true

    # Enable REST API user enumeration (default in WP 5.x)
    # DMZ-19: /wp-json/wp/v2/users is publicly accessible

    # Activate bundled vulnerable plugins (pre-copied in Dockerfile)
    echo "[entrypoint-vuln] Activating vulnerable plugins..."

    # Mail Masta 1.0 — LFI vulnerability (CVE-2016-10956)
    # DMZ-15: /wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/etc/passwd
    wp plugin activate mail-masta --path=/var/www/html --allow-root 2>/dev/null || \
        echo "[entrypoint-vuln] mail-masta activation skipped (may already be active)"

    echo "[entrypoint-vuln] Vulnerable WordPress setup complete."
else
    echo "[entrypoint-vuln] WordPress already installed, skipping setup."
fi

# Keep apache in foreground
wait $WP_PID
