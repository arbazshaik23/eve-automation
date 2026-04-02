import os
from netbox_client import *

SITE_NAME = "EVE-LAB"

site = get_or_create_site(SITE_NAME)

files = [f for f in os.listdir("/root/eve-automation/ansible/Netbox_Data") if f.endswith(".txt")]

for file in files:
    hostname = file.replace(".txt", "")

    device = get_or_create_device(hostname, site)

    with open(f"/root/eve-automation/ansible/Netbox_Data/{file}") as f:
        lines = f.readlines()

    for line in lines:
        parts = line.split()

        if len(parts) < 2:
            continue

        interface_name = parts[0]
        ip_address = parts[1]

        if ip_address == "unassigned":
            continue

        iface = create_interface(device, interface_name)

        print(f"Created/found interface {interface_name} (ID: {iface.id}) on {device.name}")

        create_ip(f"{ip_address}/24", iface)

        print(f"Assigned IP {ip_address}/24 to {interface_name}")

print("Import complete")