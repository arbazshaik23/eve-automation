import os
import subprocess
from openai import OpenAI

# 1. Initialize OpenAI Client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_available_playbooks():
    """Returns a list of .yml files in the Playbooks folder"""
    path = "./Playbooks"
    return [f for f in os.listdir(path) if f.endswith('.yml')]

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
        messages=[{"role": "system", "content": system_prompt}]
    )
    return response.choices[0].message.content.strip()

def run_ansible(playbook_name):
    """Executes the chosen playbook"""
    print(f"--- 🚀 Executing: {playbook_name} ---")
    cmd = ["ansible-playbook", "-i", "inventory.ini", f"Playbooks/{playbook_name}"]
    subprocess.run(cmd)

# --- MAIN LOOP ---
if __name__ == "__main__":
    playbooks = get_available_playbooks()
    user_req = input("What do you want to do in the lab? ")
    
    chosen_file = ask_ai_for_playbook(user_req, playbooks)
    
    if chosen_file != "NONE" and chosen_file in playbooks:
        run_ansible(chosen_file)
    else:
        print(f"AI couldn't find a match. It suggested: {chosen_file}")
