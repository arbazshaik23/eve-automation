# provision_new_site.py  —  MODE 2: Allocate and build a new site
import subprocess
from netbox_client import *

# ── Supernet IDs from your NetBox instance ──────────────────────────
# Find these in NetBox under IPAM > Prefixes, note the ID in the URL
SUPERNET_P2P_ID   = 1    # e.g. 10.100.0.0/16  point-to-point /30s
SUPERNET_LO_ID    = 2    # e.g. 10.200.0.0/16  loopbacks /32s
SUPERNET_LAN_ID   = 3    # e.g. 172.16.0.0/16  LAN segments /24s
SUPERNET_MGMT_ID  = 4    # e.g. 192.168.0.0/16 management /24s


def allocate_next_prefix(supernet_id, prefix_length, site_name, description):
    """
    Ask NetBox for the next available prefix from a supernet pool,
    create it as Active immediately to reserve it, and return the prefix.
    """
    # Step 1 — ask NetBox what is available
    available = nb.ipam.prefixes.get(supernet_id).available_prefixes.list()

    # Step 2 — find the first block that fits our prefix_length
    for candidate in available:
        if candidate["prefix_length"] <= prefix_length:
            # Step 3 — create (reserve) it immediately
            reserved = nb.ipam.prefixes.create({
                "prefix":      candidate["prefix"],
                "status":      "active",
                "description": description,
                "tags":        [{"name": site_name}]
            })
            print(f"  Allocated : {reserved.prefix} for {description}")
            return reserved

    raise Exception(f"No available /{prefix_length} in supernet ID {supernet_id}")


def get_host_ips(prefix_str, count=2):
    """
    Given a prefix like '10.100.0.0/30' return the first N host IPs.
    10.100.0.0/30 → ['10.100.0.1/30', '10.100.0.2/30']
    """
    import ipaddress
    network = ipaddress.ip_network(prefix_str, strict=False)
    hosts   = list(network.hosts())
    return [f"{hosts[i]}/{network.prefixlen}" for i in range(count)]


def run_ansible_provision(site_name, site_vars):
    """
    Call the Ansible provisioning playbook passing site variables.
    """
    extra_vars = " ".join([f"{k}={v}" for k, v in site_vars.items()])
    cmd = [
        "ansible-playbook",
        "-i", "ansible/Inventories/hosts.ini",
        "ansible/Playbooks/provision_site.yml",
        "--extra-vars", extra_vars
    ]
    print(f"\n--- Running Ansible provisioning for {site_name} ---")
    subprocess.run(cmd)


def provision_site(site_name):
    print(f"\n====== Provisioning: {site_name} ======")

    # 1. Ensure site exists in NetBox
    site = get_or_create_site(site_name)

    # 2. Allocate all required prefixes from supernets
    p2p_prefix  = allocate_next_prefix(SUPERNET_P2P_ID,  30, site_name, f"{site_name} P2P")
    lo_prefix   = allocate_next_prefix(SUPERNET_LO_ID,   32, site_name, f"{site_name} Loopback")
    lan_prefix  = allocate_next_prefix(SUPERNET_LAN_ID,  24, site_name, f"{site_name} LAN")
    mgmt_prefix = allocate_next_prefix(SUPERNET_MGMT_ID, 24, site_name, f"{site_name} Management")

    # 3. Calculate individual IPs from the allocated /30
    p2p_ips = get_host_ips(p2p_prefix.prefix, count=2)

    # 4. Build the variable map to pass to Ansible
    site_vars = {
        "site_name":        site_name,
        "p2p_tunnel_ip_a":  p2p_ips[0],       # e.g. 10.100.0.1/30
        "p2p_tunnel_ip_b":  p2p_ips[1],       # e.g. 10.100.0.2/30
        "loopback_ip":      lo_prefix.prefix,  # e.g. 10.200.0.1/32
        "lan_prefix":       lan_prefix.prefix, # e.g. 172.16.1.0/24
        "mgmt_prefix":      mgmt_prefix.prefix # e.g. 192.168.1.0/24
    }

    print(f"\n  Site variables allocated:")
    for k, v in site_vars.items():
        print(f"    {k:<20} = {v}")

    # 5. Pass variables to Ansible to render and push configs
    run_ansible_provision(site_name, site_vars)

    print(f"\n====== {site_name} provisioning complete ======")


if __name__ == "__main__":
    site_name = input("Enter site name (e.g. arizona-site-100): ").strip()
    provision_site(site_name)