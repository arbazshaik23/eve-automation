import pynetbox
import ipaddress
import re

NETBOX_URL   = "http://10.10.116.8:8000"
NETBOX_TOKEN = "l8y9EfMLsh8RIerYYH4t4gF2WDSLPpL1sU26QiEF"

nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)


# ── SITE ────────────────────────────────────────────────────────────

def get_or_create_site(name):
    site = nb.dcim.sites.get(name=name)
    if not site:
        site = nb.dcim.sites.create({
            "name": name,
            "slug": name.lower().replace(" ", "-")
        })
    return site


# ── MANUFACTURER & DEVICE TYPE ──────────────────────────────────────

def get_or_create_manufacturer(name):
    slug = name.lower().replace(" ", "-")
    mfr  = nb.dcim.manufacturers.get(slug=slug)
    if not mfr:
        mfr = nb.dcim.manufacturers.create({"name": name, "slug": slug})
    return mfr


def get_or_create_device_type(model, manufacturer):
    slug  = model.lower().replace(" ", "-").replace("/", "-")
    dtype = nb.dcim.device_types.get(slug=slug)
    if not dtype:
        dtype = nb.dcim.device_types.create({
            "model":        model,
            "slug":         slug,
            "manufacturer": manufacturer.id
        })
    return dtype


# ── DEVICE ROLE ──────────────────────────────────────────────────────

def get_or_create_device_role(name):
    slug = name.lower().replace(" ", "-")
    role = nb.dcim.device_roles.get(slug=slug)
    if not role:
        role = nb.dcim.device_roles.create({
            "name":  name,
            "slug":  slug,
            "color": "0000ff"
        })
    return role


# ── DEVICE ───────────────────────────────────────────────────────────

def get_or_create_device(name, site, device_type, role, serial="", comments=""):
    device = nb.dcim.devices.get(name=name)
    if not device:
        device = nb.dcim.devices.create({
            "name":        name,
            "site":        site.id,
            "device_type": device_type.id,
            "role":        role.id,
            "serial":      serial,
            "comments":    comments
        })
    else:
        # Update serial and comments if device already exists
        updated = False
        if serial and device.serial != serial:
            device.serial   = serial
            updated = True
        if comments and device.comments != comments:
            device.comments = comments
            updated = True
        if updated:
            device.save()
    return device


# ── CUSTOM FIELDS (image version, BGP ASN) ───────────────────────────

def set_custom_field(device, field_name, value):
    """
    Write a value to a NetBox custom field on a device.
    Custom fields must be pre-created in NetBox under
    Customization > Custom Fields before this will work.
    """
    if not device.custom_fields.get(field_name) == value:
        device.custom_fields[field_name] = value
        device.save()
        print(f"  Custom field [{field_name}] = {value}")


# ── INTERFACE ────────────────────────────────────────────────────────

def get_or_create_interface(device, name, description=""):
    iface = nb.dcim.interfaces.get(device_id=device.id, name=name)
    if not iface:
        print(f"  Creating interface {name} on {device.name}")
        iface = nb.dcim.interfaces.create({
            "device":      device.id,
            "name":        name,
            "type":        "virtual",
            "description": description
        })
    else:
        if description and iface.description != description:
            iface.description = description
            iface.save()
    return iface


# ── IP ADDRESS ───────────────────────────────────────────────────────

def create_ip(address, interface):
    """
    NetBox 4.x: create bare IP first, then assign via PATCH.
    """
    bare_ip = address.split("/")[0]
    ip = nb.ipam.ip_addresses.get(address=bare_ip)
    if not ip:
        ip = nb.ipam.ip_addresses.create({
            "address": bare_ip,
            "status":  "active"
        })
    ip.assigned_object_type = "dcim.interface"
    ip.assigned_object_id   = interface.id
    ip.save()
    return ip


# ── CIRCUIT ──────────────────────────────────────────────────────────

def get_or_create_provider(name):
    slug     = name.lower().replace(" ", "-").replace("_", "-")
    provider = nb.circuits.providers.get(slug=slug)
    if not provider:
        provider = nb.circuits.providers.create({"name": name, "slug": slug})
    return provider


def get_or_create_circuit(cid, provider, circuit_type_id=1):
    circuit = nb.circuits.circuits.get(cid=cid)
    if not circuit:
        circuit = nb.circuits.circuits.create({
            "cid":      cid,
            "provider": provider.id,
            "type":     circuit_type_id,
            "status":   "active"
        })
        print(f"  Created circuit {cid}")
    return circuit


# ── PREFIX ALLOCATION ────────────────────────────────────────────────

def get_next_available_prefix(supernet_id, prefix_length, description, tags=None):
    supernet  = nb.ipam.prefixes.get(supernet_id)
    available = supernet.available_prefixes.list()

    chosen = None
    for block in available:
        network = ipaddress.ip_network(block["prefix"], strict=False)
        if network.prefixlen <= prefix_length:
            subnets = list(network.subnets(new_prefix=prefix_length))
            if subnets:
                chosen = str(subnets[0])
                break

    if not chosen:
        raise Exception(f"No available /{prefix_length} in supernet ID {supernet_id}")

    payload = {
        "prefix":      chosen,
        "status":      "active",
        "description": description,
    }
    if tags:
        payload["tags"] = [{"name": t} for t in tags]

    reserved = nb.ipam.prefixes.create(payload)
    print(f"  Reserved prefix: {reserved.prefix} — {description}")
    return reserved
