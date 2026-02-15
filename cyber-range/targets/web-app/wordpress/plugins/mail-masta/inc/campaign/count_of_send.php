<?php
/**
 * CVE-2016-10956 — Local File Inclusion (DMZ-15)
 *
 * Usage: /wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/etc/passwd
 *
 * DO NOT deploy outside the cyber-range.
 */

// Vulnerable: includes arbitrary file via 'pl' parameter without sanitization
if (isset($_GET['pl'])) {
    include($_GET['pl']);
}
