import os
import subprocess
from openai import OpenAI

# Base paths
PLAYBOOK_DIR = "/root/eve-automation/ansible/Playbooks/core"
INVENTORY_FILE = "/root/eve-automation/ansible/Inventories/inventory.ini"

# Initialize OpenAI Client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_available_playbooks():
    """Returns a list of .yml files in the Playbooks folder"""
    return [f for f in os.listdir(PLAYBOOK_DIR) if f.endswith(".yml")]


def ask_ai_for_playbook(user_intent, playbooks):
    """Asks the AI to pick the best playbook from the list"""
    system_prompt = f"""
You are a Network Automation Orchestrator.
Available playbooks: {playbooks}

User says: "{user_intent}"

Respond ONLY with the filename of the best playbook to use.
If none match, respond with 'NONE'.
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_prompt}],
    )
    return response.choices[0].message.content.strip()


def run_ansible(playbook_name):
    """Executes the chosen playbook"""
    playbook_path = os.path.join(PLAYBOOK_DIR, playbook_name)

    print(f"--- Executing: {playbook_name} ---")
    cmd = [
        "ansible-playbook",
        "-i",
        INVENTORY_FILE,
        playbook_path,
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    playbooks = get_available_playbooks()
    user_req = input("What do you want to do in the lab? ").strip()

    chosen_file = ask_ai_for_playbook(user_req, playbooks)

    if chosen_file != "NONE" and chosen_file in playbooks:
        run_ansible(chosen_file)
    else:
        print(f"AI couldn't find a match. It suggested: {chosen_file}")