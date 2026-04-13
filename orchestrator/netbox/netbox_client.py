import pynetbox
import ipaddress
import re

NETBOX_URL   = "http://10.10.116.8:8000"
NETBOX_TOKEN = "insert-key-here"

nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)


# ── SITE ─────────────────────────────────────────────────────────────

def get_or_create_site(name):
    site = nb.dcim.sites.get(name=name)
    if not site:
        site = nb.dcim.sites.create({
            "name": name,
            "slug": name.lower().replace(" ", "-")
        })
        print(f"  [CREATED] Site: {name}")
    else:
        print(f"  [EXISTS]  Site: {name}")
    return site


# ── MANUFACTURER ──────────────────────────────────────────────────────

def get_or_create_manufacturer(name):
    slug = name.lower().replace(" ", "-")
    mfr  = nb.dcim.manufacturers.get(slug=slug)
    if not mfr:
        mfr = nb.dcim.manufacturers.create({"name": name, "slug": slug})
        print(f"  [CREATED] Manufacturer: {name}")
    return mfr


# ── DEVICE TYPE ───────────────────────────────────────────────────────

def get_or_create_device_type(model, manufacturer):
    slug  = model.lower().replace(" ", "-").replace("/", "-")
    dtype = nb.dcim.device_types.get(slug=slug)
    if not dtype:
        dtype = nb.dcim.device_types.create({
            "model":        model,
            "slug":         slug,
            "manufacturer": manufacturer.id
        })
        print(f"  [CREATED] Device Type: {model}")
    return dtype


# ── DEVICE ROLE ───────────────────────────────────────────────────────

def get_or_create_device_role(name):
    slug = name.lower().replace(" ", "-")
    role = nb.dcim.device_roles.get(slug=slug)
    if not role:
        role = nb.dcim.device_roles.create({
            "name":  name,
            "slug":  slug,
            "color": "0000ff"
        })
        print(f"  [CREATED] Device Role: {name}")
    return role


# ── DEVICE ────────────────────────────────────────────────────────────

def get_or_create_device(name, site, device_type, role, serial="", comments=""):
    device  = nb.dcim.devices.get(name=name)
    changes = {}

    if not device:
        device = nb.dcim.devices.create({
            "name":        name,
            "site":        site.id,
            "device_type": device_type.id,
            "role":        role.id,
            "serial":      serial,
            "comments":    comments
        })
        print(f"  [CREATED] Device: {name}")
        return device

    # Device exists — only update fields that have changed
    if serial   and device.serial   != serial:   changes["serial"]   = serial
    if comments and device.comments != comments: changes["comments"] = comments

    if changes:
        for field, value in changes.items():
            setattr(device, field, value)
        device.save()
        print(f"  [UPDATED] Device {name}: {list(changes.keys())}")
    else:
        print(f"  [EXISTS]  Device: {name} — no changes")

    return device


# ── CUSTOM FIELDS ─────────────────────────────────────────────────────

def set_custom_field(device, field_name, value):
    """
    Only writes to NetBox if the value has actually changed.
    Custom fields must be pre-created in NetBox UI before use.
    """
    current = device.custom_fields.get(field_name)
    if current != value:
        device.custom_fields[field_name] = value
        device.save()
        print(f"  [UPDATED] Custom field [{field_name}]: {current} → {value}")
    else:
        print(f"  [EXISTS]  Custom field [{field_name}]: {value}")


# ── INTERFACE ─────────────────────────────────────────────────────────

def get_or_create_interface(device, name, description=""):
    iface   = nb.dcim.interfaces.get(device_id=device.id, name=name)
    changes = {}

    if not iface:
        iface = nb.dcim.interfaces.create({
            "device":      device.id,
            "name":        name,
            "type":        "virtual",
            "description": description
        })
        print(f"    [CREATED] Interface: {name}")
        return iface

    # Only update description if it has changed and is non-empty
    if description and iface.description != description:
        changes["description"] = description

    if changes:
        for field, value in changes.items():
            setattr(iface, field, value)
        iface.save()
        print(f"    [UPDATED] Interface {name}: {list(changes.keys())}")
    else:
        print(f"    [EXISTS]  Interface: {name}")

    return iface


# ── IP ADDRESS ────────────────────────────────────────────────────────

def create_ip(address, interface):
    """
    NetBox 4.x: create bare IP first, assign via PATCH separately.
    Only updates the interface assignment if it has changed.
    """
    bare_ip = address.split("/")[0]
    ip      = nb.ipam.ip_addresses.get(address=bare_ip)

    if not ip:
        ip = nb.ipam.ip_addresses.create({
            "address": bare_ip,
            "status":  "active"
        })
        print(f"    [CREATED] IP: {bare_ip}")
    else:
        print(f"    [EXISTS]  IP: {bare_ip}")

    # Only PATCH the assignment if it is not already correct
    already_assigned = (
        ip.assigned_object_id   == interface.id and
        ip.assigned_object_type == "dcim.interface"
    )
    if not already_assigned:
        ip.assigned_object_type = "dcim.interface"
        ip.assigned_object_id   = interface.id
        ip.save()
        print(f"    [UPDATED] IP {bare_ip} assigned to {interface.name}")

    return ip


# ── VLAN ──────────────────────────────────────────────────────────────

def get_or_create_vlan(vlan_id, name, site):
    vlan = nb.ipam.vlans.get(vid=vlan_id, site_id=site.id)
    if not vlan:
        vlan = nb.ipam.vlans.create({
            "vid":  vlan_id,
            "name": name,
            "site": site.id
        })
        print(f"  [CREATED] VLAN {vlan_id}: {name}")
    else:
        print(f"  [EXISTS]  VLAN {vlan_id}: {name}")
    return vlan


# ── CIRCUIT PROVIDER ──────────────────────────────────────────────────

def get_or_create_provider(name):
    slug     = name.lower().replace(" ", "-").replace("_", "-")
    provider = nb.circuits.providers.get(slug=slug)
    if not provider:
        provider = nb.circuits.providers.create({"name": name, "slug": slug})
        print(f"  [CREATED] Provider: {name}")
    else:
        print(f"  [EXISTS]  Provider: {name}")
    return provider


# ── CIRCUIT ───────────────────────────────────────────────────────────

def get_or_create_circuit(cid, provider, circuit_type_id=1):
    circuit = nb.circuits.circuits.get(cid=cid)
    if not circuit:
        circuit = nb.circuits.circuits.create({
            "cid":      cid,
            "provider": provider.id,
            "type":     circuit_type_id,
            "status":   "active"
        })
        print(f"  [CREATED] Circuit: {cid}")
    else:
        print(f"  [EXISTS]  Circuit: {cid}")
    return circuit


# ── PREFIX ALLOCATION ─────────────────────────────────────────────────

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
        raise Exception(
            f"No available /{prefix_length} in supernet ID {supernet_id}"
        )

    payload = {
        "prefix":      chosen,
        "status":      "active",
        "description": description,
    }
    if tags:
        payload["tags"] = [{"name": t} for t in tags]

    reserved = nb.ipam.prefixes.create(payload)
    print(f"  [CREATED] Prefix: {reserved.prefix} — {description}")
    return reserved