# import_eve_lab.py  —  MODE 1: Sync existing devices into NetBox
import os
from netbox_client import *

SITE_NAME   = "EVE-LAB"
DATA_DIR    = "/root/eve-automation/ansible/Netbox_Data"

def sync_device_from_file(filepath, site):
    """Read a single device .txt file and sync it into NetBox."""
    hostname = os.path.basename(filepath).replace(".txt", "")
    print(f"\n--- Syncing device: {hostname} ---")
    device = get_or_create_device(hostname, site)

    with open(filepath) as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        if parts[0] in ("Interface", "interface") or parts[1] == "IP-Address":
            continue

        interface_name = parts[0]
        ip_address     = parts[1]

        if ip_address.lower() == "unassigned":
            continue

        # Normalise prefix — use what the file provides, default /24
        if "/" not in ip_address:
            ip_address = f"{ip_address}/24"

        iface = create_interface(device, interface_name)
        print(f"  Interface : {interface_name} (ID: {iface.id})")

        ip = create_ip(ip_address, iface)
        print(f"  IP        : {ip.address} on {iface.name}")

    return device


def main():
    site  = get_or_create_site(SITE_NAME)
    files = [
        os.path.join(DATA_DIR, f)
        for f in os.listdir(DATA_DIR)
        if f.endswith(".txt")
    ]

    if not files:
        print(f"No .txt files found in {DATA_DIR}")
        return

    for filepath in files:
        sync_device_from_file(filepath, site)

    print("\nImport complete.")


if __name__ == "__main__":
    main()