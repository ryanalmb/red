# =============================================================================
# Deliberately Vulnerable WordPress — Cyber Range Tier 1 (DMZ)
# =============================================================================
# DO NOT deploy outside the cyber-range. Every flaw is intentional.
#
# Based on WordPress 5.7 with vulnerable plugins pre-installed:
#   - Mail Masta 1.0 (CVE-2016-10956 — LFI)
#   - Survey 1.5.7 (SQLi)
#   - Theme with directory traversal
#
# Vulnerabilities:
#   DMZ-13  XML-RPC brute force (enabled, no lockout)
#   DMZ-14  User enumeration (?author=1)
#   DMZ-15  Plugin RCE — Mail Masta LFI (CVE-2016-10956)
#   DMZ-16  Plugin SQLi — Survey
#   DMZ-17  Theme directory traversal
#   DMZ-18  wp-config.php database creds exposed via LFI
#   DMZ-19  Unauthenticated REST API user enumeration
#   DMZ-20  PHP Object Injection
#   DMZ-21  XXE in XML-RPC
#   DMZ-22  Weak admin credentials (admin/admin123)
# =============================================================================

FROM wordpress:5.7-php7.4-apache

# Enable XML-RPC (intentional — brute force + XXE vector)
RUN echo "# XML-RPC enabled for DMZ-13, DMZ-21" > /var/www/html/.htaccess

# Install WP-CLI for plugin/theme setup (best-effort — network may be unavailable)
RUN curl -sfL -o wp-cli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar \
    && chmod +x wp-cli.phar \
    && mv wp-cli.phar /usr/local/bin/wp \
    || echo "WP-CLI download skipped — plugin is pre-bundled, WP setup will use defaults"

# Bundle vulnerable plugins locally (no internet required at runtime)
COPY plugins/mail-masta /var/www/html/wp-content/plugins/mail-masta

# Setup script run at container start
COPY entrypoint-vuln.sh /usr/local/bin/entrypoint-vuln.sh
RUN chmod +x /usr/local/bin/entrypoint-vuln.sh

EXPOSE 80

ENTRYPOINT ["entrypoint-vuln.sh"]
CMD ["apache2-foreground"]
