<?php
/**
 * Second LFI vector in Mail Masta (bonus — same CVE)
 *
 * Usage: /wp-content/plugins/mail-masta/inc/lists/csvexport.php?pl=/etc/passwd
 *
 * DO NOT deploy outside the cyber-range.
 */

if (isset($_GET['pl'])) {
    include($_GET['pl']);
}
