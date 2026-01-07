#!/usr/bin/env python3
"""Categorize Kali tools into security categories.

This script reads tool names from stdin and outputs a YAML manifest
with tools organized by category.
"""
import sys
import yaml
import datetime

# Common Linux utilities to exclude (expanded list)
EXCLUDES = {
    # Core utils
    "apt", "apt-get", "bash", "cat", "cd", "chmod", "chown", "cp", "date", "dd", "df", "diff",
    "echo", "find", "grep", "gzip", "kill", "ln", "ls", "mkdir", "mv", "ps", "pwd", "rm", 
    "rmdir", "sed", "sh", "sleep", "sort", "stat", "su", "sudo", "tar", "touch", "uname", 
    "vi", "vim", "wc", "which", "whoami", "yes", "dpkg", "dpkg-query", "mount", "umount",
    "chgrp", "install", "mktemp", "readlink", "run-parts", "tempfile", "zcat",
    "base64", "basename", "dirname", "env", "false", "groups", "head", "id", "link",
    "logname", "nice", "nohup", "od", "passwd", "paste", "pr", "printenv", "printf",
    "tail", "tee", "test", "tr", "true", "tsort", "tty", "uniq", "unlink", "users", "who",
    "xargs", "clear", "reset", "python", "python3", "perl", "ruby", "awk", "gawk", "mawk",
    "less", "more", "zgrep", "zless", "zmore", "adduser", "addgroup", "deluser", "delgroup",
    "chroot", "dmesg", "hostname", "uptime", "free", "top", "htop", "nano", "ed",
    # System tools that aren't security-related  
    "systemctl", "journalctl", "loginctl", "hostnamectl", "timedatectl", "localectl",
    "apt-cache", "apt-config", "apt-key", "update-alternatives", "update-rc.d",
    # Common dev tools
    "git", "make", "gcc", "g++", "go", "cargo", "npm", "pip", "pip3", "gem",
    "curl", "wget",  # These are kept out as they're too generic
}

# Comprehensive tool-to-category mappings
TOOL_CATEGORIES = {
    # ========== RECONNAISSANCE ==========
    "reconnaissance": {
        # Port/Network Scanners
        "nmap", "masscan", "unicornscan", "zmap", "rustscan", "sx",
        # DNS/Subdomain
        "subfinder", "amass", "dnsenum", "dnsrecon", "dnsmap", "fierce", "dnsx",
        "sublist3r", "findomain", "assetfinder", "massdns", "shuffledns", "puredns",
        # OSINT
        "theharvester", "maltego", "recon-ng", "spiderfoot", "shodan", "censys",
        "whois", "dig", "nslookup", "host",
        # Network Discovery
        "netdiscover", "arp-scan", "arping", "fping", "hping3", "ping",
        "traceroute", "mtr", "tcptraceroute",
        # Enumeration
        "enum4linux", "enum4linux-ng", "nbtscan", "smbmap", "rpcclient", "ldapsearch",
        "snmpwalk", "snmp-check", "onesixtyone",
        # Banner Grabbing
        "whatweb", "wafw00f", "httprobe", "httpx", "httpx-toolkit",
    },
    
    # ========== WEB APPLICATION ==========
    "web_application": {
        # Web Fuzzers/Scanners
        "ffuf", "gobuster", "dirb", "dirbuster", "wfuzz", "feroxbuster",
        "nikto", "skipfish", "wapiti", "arachni", "zaproxy", "zap",
        # SQL Injection
        "sqlmap", "sqlninja", "bbqsql", "jsql",
        # XSS
        "xsser", "dalfox", "xsstrike",
        # CMS Scanners
        "wpscan", "joomscan", "droopescan", "cmsmap",
        # Proxy/Interception
        "burpsuite", "mitmproxy", "proxychains", "proxychains4",
        # Web Shells/Exploitation
        "commix", "weevely", "webshells",
        # API Testing
        "postman", "insomnia", "arjun", "paramspider",
        # Other Web
        "nuclei", "gospider", "hakrawler", "katana", "gau", "waybackurls",
    },
    
    # ========== EXPLOITATION ==========
    "exploitation": {
        # Metasploit Family
        "msfconsole", "msfvenom", "msfdb", "msfrpc", "msfd", "msfupdate",
        "metasploit", "metasploit-framework",
        # Exploit Databases
        "searchsploit", "exploitdb", "exploitdb-papers",
        # Password Attacks
        "hydra", "medusa", "ncrack", "patator", "crowbar",
        "john", "johnny", "hashcat", "hashid", "hash-identifier", "hashcat-utils",
        "ophcrack", "rainbowcrack",
        # Shells/Payloads
        "msfvenom", "veil", "shellter", "unicorn",
        # Network Exploitation
        "responder", "impacket-scripts", "crackmapexec", "cme",
        "evil-winrm", "psexec.py", "wmiexec.py", "smbexec.py", "atexec.py",
        "secretsdump.py", "getTGT.py", "getST.py", "GetNPUsers.py", "GetUserSPNs.py",
        # Vulnerability Scanners
        "openvas", "nessus", "nikto",
    },
    
    # ========== POST EXPLOITATION ==========
    "post_exploitation": {
        # Privilege Escalation
        "linpeas", "linenum", "linux-exploit-suggester", "lse",
        "winpeas", "powerup", "beroot", "peass",
        # Credential Dumping
        "mimikatz", "pypykatz", "lsassy", "procdump",
        "secretsdump", "ntdsutil",
        # Lateral Movement
        "crackmapexec", "cme", "psexec", "wmiexec", "smbexec",
        "evil-winrm", "winrm", "rdp",
        # AD Enumeration/Attack
        "bloodhound", "bloodhound-python", "sharphound",
        "certipy", "adidnsdump", "ldapdomaindump",
        "rubeus", "kerberoast",
        # Persistence
        "empire", "starkiller", "covenant", "sliver",
        # Data Exfil
        "exfiltration", "dnscat2", "iodine",
    },
    
    # ========== WIRELESS ==========
    "wireless": {
        # Aircrack Suite
        "aircrack-ng", "aireplay-ng", "airmon-ng", "airodump-ng",
        "airbase-ng", "airdecap-ng", "airdecloak-ng", "airolib-ng",
        "airgraph-ng", "airserv-ng", "airtun-ng", "besside-ng",
        "packetforge-ng", "wesside-ng", "easside-ng",
        # WiFi Attack Tools
        "wifite", "wifite2", "fluxion", "airgeddon", "wifiphisher",
        "fern-wifi-cracker", "linset",
        # WPS
        "reaver", "bully", "pixiewps", "wash",
        # Bluetooth
        "btscanner", "blueranger", "bluelog", "spooftooph",
        "hcitool", "hciconfig", "l2ping", "rfcomm",
        # Other Wireless
        "kismet", "wireshark", "tshark", "horst",
        "mdk3", "mdk4", "cowpatty", "pyrit",
    },
    
    # ========== NETWORK TOOLS ==========
    "network": {
        # Sniffing/Capture
        "tcpdump", "wireshark", "tshark", "ettercap", "bettercap",
        "dsniff", "arpspoof", "macchanger",
        # Netcat variants
        "netcat", "nc", "ncat", "socat", "cryptcat",
        # Tunneling
        "ssh", "sshpass", "sshuttle", "chisel", "ligolo",
        "stunnel", "proxytunnel",
        # VPN
        "openvpn", "wireguard", "ipsec",
        # SMB/Windows
        "smbclient", "smbget", "smbtar", "rpcclient",
        "nmblookup", "net", "winexe", "pth-winexe",
        # FTP/TFTP
        "ftp", "tftp", "atftp",
        # Other
        "telnet", "rdesktop", "xfreerdp", "freerdp",
    },
    
    # ========== FORENSICS ==========
    "forensics": {
        "autopsy", "sleuthkit", "foremost", "scalpel",
        "binwalk", "bulk_extractor", "testdisk", "photorec",
        "volatility", "volatility3", "rekall",
        "strings", "xxd", "hexdump", "objdump",
        "exiftool", "pdfparser", "pdf-parser", "peepdf",
        "yara", "clamav", "chkrootkit", "rkhunter",
    },
    
    # ========== REVERSE ENGINEERING ==========
    "reverse_engineering": {
        "ghidra", "radare2", "r2", "rizin", "cutter",
        "gdb", "gdb-peda", "pwndbg", "gef",
        "objdump", "readelf", "nm", "ldd",
        "ltrace", "strace", "dtruss",
        "upx", "jadx", "apktool", "dex2jar",
        "ida", "hopper", "binary-ninja",
    },
}

def get_category(tool_name: str) -> str:
    """Determine the category for a tool."""
    tool_lower = tool_name.lower()
    
    # Direct lookup in category sets
    for category, tools in TOOL_CATEGORIES.items():
        if tool_lower in tools:
            return category
    
    # Heuristic matching based on prefixes/patterns
    heuristics = [
        # Reconnaissance patterns
        (["scan", "enum", "recon", "dns", "whois", "discover"], "reconnaissance"),
        # Web patterns
        (["web", "sql", "xss", "http", "fuzz", "proxy", "cms", "php"], "web_application"),
        # Exploitation patterns
        (["exploit", "msf", "shell", "payload", "venom", "crack", "brute"], "exploitation"),
        # Post-exploitation patterns
        (["peas", "priv", "dump", "lateral", "persist", "empire"], "post_exploitation"),
        # Wireless patterns
        (["wifi", "air", "wlan", "wep", "wpa", "bluetooth", "blue", "rf"], "wireless"),
        # Network patterns
        (["net", "tcp", "udp", "sniff", "spoof", "tunnel", "vpn"], "network"),
        # Forensics patterns
        (["forensic", "carve", "recover", "memory", "disk", "image"], "forensics"),
        # Reverse engineering patterns
        (["debug", "disasm", "decompile", "binary", "elf", "pe"], "reverse_engineering"),
    ]
    
    for patterns, category in heuristics:
        if any(p in tool_lower for p in patterns):
            return category
    
    return "other"


def main():
    tools_list = []
    for line in sys.stdin:
        tool_name = line.strip()
        if not tool_name:
            continue
        if tool_name.lower() in EXCLUDES:
            continue
        if tool_name.startswith("dpkg-") or tool_name.startswith("apt-"):
            continue
        # Filter out library/config files
        if tool_name.endswith(".so") or tool_name.endswith(".conf"):
            continue
        tools_list.append(tool_name)

    # Initialize categories with the defined ones + other
    categories = {}
    for cat_name in list(TOOL_CATEGORIES.keys()) + ["other"]:
        categories[cat_name] = {
            "description": get_category_description(cat_name),
            "tools": []
        }

    all_tools_flat = []

    for name in sorted(list(set(tools_list))):  # Deduplicate
        category = get_category(name)
        tool_entry = {
            "name": name,
            "description": f"Auto-detected tool: {name}",
            "common_flags": [],
            "output_format": "stdout"
        }
        categories[category]["tools"].append(tool_entry)
        all_tools_flat.append(tool_entry)

    manifest = {
        "version": "1.0",
        "generated": datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
        "tool_count": len(all_tools_flat),
        "categories": categories,
        "tools": all_tools_flat 
    }

    print(yaml.dump(manifest, sort_keys=False, allow_unicode=True))


def get_category_description(category: str) -> str:
    """Get human-readable description for a category."""
    descriptions = {
        "reconnaissance": "Network and host discovery, OSINT, enumeration",
        "web_application": "Web application testing, fuzzing, SQL injection",
        "exploitation": "Vulnerability exploitation, password attacks, payloads",
        "post_exploitation": "Privilege escalation, lateral movement, persistence",
        "wireless": "WiFi, Bluetooth, and RF testing tools",
        "network": "Network sniffing, tunneling, protocol tools",
        "forensics": "Digital forensics and incident response",
        "reverse_engineering": "Binary analysis, debugging, decompilation",
        "other": "Uncategorized tools",
    }
    return descriptions.get(category, "Uncategorized tools")


if __name__ == "__main__":
    main()
