# import_eve_lab.py
import os
import json
import re
from netbox_client import *

SITE_NAME = "EVE-LAB"
DATA_DIR  = "/root/eve-automation/ansible/Netbox_Data"


# ── PARSERS ──────────────────────────────────────────────────────────

def parse_show_version(raw):
    """
    Extract hostname, model, serial number, and IOS image from
    'show version' output.
    Returns a dict with keys: hostname, model, serial, image
    """
    result = {"hostname": "", "model": "", "serial": "", "image": ""}

    # Hostname — first line: "hostname uptime is..."
    m = re.search(r'^(\S+)\s+uptime is', raw, re.MULTILINE)
    if m:
        result["hostname"] = m.group(1)

    # Model — "Cisco IOS Software ... cisco CSR1000V"
    m = re.search(r'[Cc]isco\s+([\w\-]+).*?processor', raw)
    if m:
        result["model"] = m.group(1)

    # Serial number
    m = re.search(r'[Pp]rocessor board ID\s+(\S+)', raw)
    if m:
        result["serial"] = m.group(1)

    # IOS image filename
    m = re.search(r'[Ss]ystem image file is\s+"([^"]+)"', raw)
    if m:
        result["image"] = m.group(1)

    return result


def parse_bgp_summary(raw):
    """
    Extract local BGP ASN from 'show ip bgp summary'.
    Returns ASN as string or empty string if BGP not running.
    """
    m = re.search(r'local AS number\s+(\d+)', raw, re.IGNORECASE)
    return m.group(1) if m else ""


def parse_vlan_brief(raw):
    """
    Extract VLANs from 'show vlan brief'.
    Returns list of dicts: [{"id": 10, "name": "MGMT"}, ...]
    Skips default VLANs 1, 1002-1005.
    """
    vlans = []
    skip  = {1, 1002, 1003, 1004, 1005}
    for line in raw.splitlines():
        m = re.match(r'^(\d+)\s+(\S+)\s+active', line)
        if m:
            vid = int(m.group(1))
            if vid not in skip:
                vlans.append({"id": vid, "name": m.group(2)})
    return vlans


def parse_interface_descriptions(raw):
    """
    Extract interface name and description from 'show interfaces description'.
    Returns dict: {"GigabitEthernet1": "UPLINK TO ISP", ...}
    Only returns interfaces that have a non-empty description.
    """
    descriptions = {}
    for line in raw.splitlines():
        # Format: Interface    Status    Protocol    Description
        parts = line.split()
        if len(parts) >= 4 and not line.startswith("Interface"):
            iface_name  = parts[0]
            description = " ".join(parts[3:])
            if description:
                descriptions[iface_name] = description
    return descriptions


def parse_circuit_from_description(description):
    """
    Attempt to extract a circuit ID and provider from an interface description.
    Expects formats like:
        'CID-12345 | AT&T MPLS'
        'CIRCUIT: XYZ-999 PROVIDER: Zayo'
        'TO: PEER-ROUTER | CKT: 12345'
    Returns dict: {"cid": "...", "provider": "..."} or None
    """
    # Pattern 1: CID-##### | Provider Name
    m = re.search(r'(CID[-:\s]?\w+)\s*[|\-]\s*(.+)', description, re.IGNORECASE)
    if m:
        return {"cid": m.group(1).strip(), "provider": m.group(2).strip()}

    # Pattern 2: CIRCUIT: id PROVIDER: name
    m = re.search(r'CIRCUIT[:\s]+(\S+).*PROVIDER[:\s]+(\S+)', description, re.IGNORECASE)
    if m:
        return {"cid": m.group(1), "provider": m.group(2)}

    return None


def parse_ip_brief(raw):
    """
    Extract interface names and IPs from 'show ip interface brief'.
    Returns list of dicts: [{"interface": "Gi1", "ip": "10.0.0.1"}, ...]
    """
    entries = []
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        if parts[0] in ("Interface",) or parts[1] == "IP-Address":
            continue
        if parts[1].lower() == "unassigned":
            continue
        entries.append({"interface": parts[0], "ip": parts[1]})
    return entries


# ── MAIN SYNC FUNCTION ───────────────────────────────────────────────

def sync_device(data, site):
    print(f"\n{'='*55}")

    # 1. Parse show version for device identity
    ver     = parse_show_version(data["show_version"])
    hostname = data["hostname"]
    model    = ver["model"]   or "Unknown"
    serial   = ver["serial"]  or ""
    image    = ver["image"]   or ""

    print(f"  Device   : {hostname}")
    print(f"  Model    : {model}")
    print(f"  Serial   : {serial}")
    print(f"  Image    : {image}")

    # 2. Ensure manufacturer and device type exist
    manufacturer = get_or_create_manufacturer("Cisco")
    device_type  = get_or_create_device_type(model, manufacturer)
    role         = get_or_create_device_role("Router")

    # 3. Create or update device with serial number
    device = get_or_create_device(
        name        = hostname,
        site        = site,
        device_type = device_type,
        role        = role,
        serial      = serial,
        comments    = f"IOS Image: {image}"
    )

    # 4. Set custom fields — IOS image and BGP ASN
    #    These custom fields must be created first in NetBox UI:
    #    Customization > Custom Fields > Add
    #    Field names: ios_image (text), bgp_asn (text)
    if image:
        set_custom_field(device, "ios_image", image)

    bgp_asn = parse_bgp_summary(data["bgp_summary"])
    if bgp_asn:
        print(f"  BGP ASN  : {bgp_asn}")
        set_custom_field(device, "bgp_asn", bgp_asn)

    # 5. Sync VLANs
    vlans = parse_vlan_brief(data["vlan_brief"])
    for vlan in vlans:
        get_or_create_vlan(vlan["id"], vlan["name"], site)
        print(f"  VLAN     : {vlan['id']} — {vlan['name']}")

    # 6. Parse interface descriptions for circuits
    descriptions = parse_interface_descriptions(data["int_description"])

    # 7. Sync interfaces, IPs, and circuits
    ip_entries = parse_ip_brief(data["ip_brief"])

    for entry in ip_entries:
        iface_name  = entry["interface"]
        ip_address  = entry["ip"]
        description = descriptions.get(iface_name, "")

        # Create interface with description
        iface = get_or_create_interface(device, iface_name, description)
        print(f"  Interface: {iface_name} | {description}")

        # Assign IP
        if "/" not in ip_address:
            ip_address = f"{ip_address}/24"
        ip = create_ip(ip_address, iface)
        print(f"  IP       : {ip.address}")

        # Check if description indicates a circuit
        circuit_info = parse_circuit_from_description(description)
        if circuit_info:
            provider = get_or_create_provider(circuit_info["provider"])
            circuit  = get_or_create_circuit(circuit_info["cid"], provider)
            print(f"  Circuit  : {circuit_info['cid']} via {circuit_info['provider']}")


# ── ENTRY POINT ──────────────────────────────────────────────────────

def main():
    site  = get_or_create_site(SITE_NAME)
    files = [
        os.path.join(DATA_DIR, f)
        for f in os.listdir(DATA_DIR)
        if f.endswith(".json")
    ]

    if not files:
        print(f"No .json files found in {DATA_DIR}")
        return

    for filepath in files:
        with open(filepath) as f:
            data = json.load(f)
        sync_device(data, site)

    print(f"\n{'='*55}")
    print("Import complete.")


if __name__ == "__main__":
    main()