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
            "device_role": 1,
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
    NetBox 4.x requires a two-step process:
      1. Create (or fetch) the IP address object — no assignment yet.
      2. PATCH the IP to assign it to the interface via assigned_object_*.
    Combining both steps in a single POST causes a 500 KeyError: 'data'.
    """
    # Step 1: check if IP already exists
    ip = nb.ipam.ip_addresses.get(address=address)

    if not ip:
        # Create the IP with NO assignment in the same call
        ip = nb.ipam.ip_addresses.create({
            "address": address,
            "status": "active"
        })

    # Step 2: assign to interface (safe to re-run; overwrites with same values)
    ip.assigned_object_type = "dcim.interface"
    ip.assigned_object_id = interface.id
    ip.save()

    return ip