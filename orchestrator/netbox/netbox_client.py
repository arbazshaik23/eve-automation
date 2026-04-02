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
            "device_role": 1,   # adjust later
            "device_type": 1    # adjust later
        })
    return device

def create_interface(device, name):
    iface = nb.dcim.interfaces.get(device_id=device.id, name=name)
    if iface:
        return iface

    iface = nb.dcim.interfaces.create({
        "device": device.id,
        "name": name,
        "type": "virtual"
    })
    return iface

def create_ip(address, interface):
    ip = nb.ipam.ip_addresses.get(address=address)
    if ip:
        return ip

    return nb.ipam.ip_addresses.create(
        address=address,
        status="active",
        assigned_object_type="dcim.interface",
        assigned_object_id=interface.id,
    )
    ip.save()
    return ip
