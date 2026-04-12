import pynetbox

NETBOX_URL = "http://10.10.116.8:8000"
NETBOX_TOKEN = "l8y9EfMLsh8RIerYYH4t4gF2WDSLPpL1sU26QiEF"

nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)


def get_or_create_site(name):
    site = nb.dcim.sites.get(name=name)
    if not site:
        site = nb.dcim.sites.create({
            "name": name,
            "slug": name.lower().replace(" ", "-")
        })
    return site


def get_or_create_device(name, site, role="router"):
    device = nb.dcim.devices.get(name=name)
    if not device:
        device = nb.dcim.devices.create({
            "name": name,
            "site": site.id,
            "role": 1,          # was "device_role" in NetBox 3.x
            "device_type": 1
        })
    return device


def create_interface(device, name):
    iface = nb.dcim.interfaces.get(device_id=device.id, name=name)
    if iface:
        return iface
    print(f"Creating interface {name} on {device.name}")
    iface = nb.dcim.interfaces.create({
        "device": device.id,
        "name": name,
        "type": "virtual"
    })
    return iface


def create_ip(address, interface):
    """
    NetBox 4.x:
      - Does NOT accept prefix notation (e.g. /24) in the address field on create.
      - Assignment must be a separate PATCH after creation.
    """
    # Strip any prefix length before querying or creating
    bare_ip = address.split("/")[0]

    # Step 1: check if IP already exists (query by bare IP)
    ip = nb.ipam.ip_addresses.get(address=bare_ip)

    if not ip:
        # Create with bare IP only — no mask, no assignment
        ip = nb.ipam.ip_addresses.create({
            "address": bare_ip,
            "status": "active"
        })

    # Step 2: assign to interface via PATCH
    ip.assigned_object_type = "dcim.interface"
    ip.assigned_object_id = interface.id
    ip.save()

    return ip

    # Step 2: assign to interface (safe to re-run; overwrites with same values)
    ip.assigned_object_type = "dcim.interface"
    ip.assigned_object_id = interface.id
    ip.save()

    return ip