import pynetbox
import ipaddress

NETBOX_URL   = "http://10.10.116.8:8000"
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
            "role": 1,         # "device_role" was renamed to "role" in NetBox 4.x
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
        "name":   name,
        "type":   "virtual"
    })
    return iface


def create_ip(address, interface):
    """
    NetBox 4.x: