<?php
/**
 * Plugin Name: Mail Masta
 * Description: Deliberately vulnerable mail manager plugin (CVE-2016-10956 — LFI)
 * Version: 1.0
 * Author: Cyber Range
 *
 * DO NOT deploy outside the cyber-range.
 */

// This is a minimal reproduction of the Mail Masta 1.0 LFI vulnerability.
// The real plugin had many more features, but only the LFI matters for the range.

add_action('admin_menu', 'mail_masta_menu');

function mail_masta_menu() {
    add_menu_page(
        'Mail Masta',
        'Mail Masta',
        'manage_options',
        'mail-masta',
        'mail_masta_page'
    );
}

function mail_masta_page() {
    echo '<h1>Mail Masta</h1>';
    echo '<p>Campaign management plugin.</p>';
}
