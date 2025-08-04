import time
import state
from network import send_message
from parser import build_message

# --- handling group cmds ---
def process_creategroup(cmd, sock, args):
    # processes "creategroup"
    try:
        _, group_id, group_name, members_str = cmd.split(' ', 3)
        initial_members = set(m.strip() for m in members_str.split(','))
        initial_members.add(args.id)
        fields = {
            "TYPE": "GROUP_CREATE", 
            "FROM": args.id, 
            "GROUP_ID": group_id,
            "GROUP_NAME": group_name, 
            "MEMBERS": ",".join(initial_members),
            "TIMESTAMP": str(int(time.time())), 
            "TOKEN": f"{args.id}|9999999999|group"
        }
        msg = build_message(fields)
        for member_id in initial_members:
            ip = member_id.split('@')[1]
            send_message(sock, msg, ip, args.verbose)
        print(f"Group '{group_name}' created and invites sent.")
    except ValueError:
        print("Usage: creategroup <id> <name> <member1>,<member2>,...")

def process_updategroup(cmd, sock, args):
    try: 
        action, group_id, members_str = cmd.split(' ', 2)
        if group_id in state.groups and state.groups[group_id]['creator'] == args.id:
            members_to_act = set(m.strip() for m in members_str.split(','))
            fields = {
                "TYPE": "GROUP_UPDATE", 
                "FROM": args.id, 
                "GROUP_ID": group_id,
                "TIMESTAMP": str(int(time.time())), "TOKEN": f"{args.id}|9999999999|group"
            }
            if "add" in action:
                fields["ADD"] = ",".join(members_to_act)
            else:
                fields["REMOVE"] = ",".join(members_to_act)

            message = build_message(fields)
            current_members = state.groups[group_id]['members']
            all_recipients = current_members.union(members_to_act)
            for member_id in all_recipients:
                ip = member_id.split('@')[1]
                send_message(sock, message, ip, args.verbose)
            print(f"Group update sent for '{state.groups[group_id]['group_name']}'.")
        else:
            print("Error: Group not found or you are not the creator.")
    except ValueError:
        print("Usage: addtogroup <group_id> <user1>,<user2> OR removefromgroup <group_id> <user1>")

def process_gmsg(cmd, sock, args):
    try:
        _, group_id, content = cmd.split(' ', 2)
        if group_id in state.groups and args.id in state.groups[group_id]['members']:
            fields = {
                "TYPE": "GROUP_MESSAGE", 
                "FROM": args.id, 
                "GROUP_ID": group_id,
                "CONTENT": content, 
                "TIMESTAMP": str(int(time.time())),
                "TOKEN": f"{args.id}|9999999999|group"
            }
            message = build_message(fields)
            for member_id in state.groups[group_id]['members']:
                ip = member_id.split('@')[1]
                send_message(sock, message, ip, args.verbose)
            else:
                print("Error: You are not a member of that group or the group does not exist.")
    except ValueError:
        print("Usage: gmsg <group_id> <message>")

def process_listgroups(args):
    print("--- your groups ---")
    found = False
    for group_id, group_data in state.groups.items():
        if args.id in group_data['members']:
            found = True
            print(f"- {group_data['group_name']} ({group_id})")
            print(f"  Creator: {group_data['creator']}")
            print(f"  Members: {', '.join(group_data['members'])}")
    if not found:
        print("You are not a member of any groups.")
    print("-----------------------")

# --- handling group messages
def handle_group_create(msg, args):
    group_id = msg.get("GROUP_ID")
    members_str = msg.get("MEMBERS", "")
    members = set(m.strip() for m in members_str.split(','))
    if args.id in members:
        state.groups[group_id] = {
            "group_name": msg.get("GROUP_NAME"),
            "members": members,
            "creator": msg.get("FROM")
        }
        if msg.get("FROM") != args.id:
            print(f"\nYou've been added to group '{msg.get('GROUP_NAME')}' ({group_id}).")
            print(f"> ", end="", flush=True)

def handle_group_update(msg):
    group_id = msg.get("GROUP_ID")
    if group_id in state.groups:
        group = state.groups[group_id]
        if msg.get("FROM") == group['creator']:
            to_add = set(m.strip() for m in msg.get("REMOVE", "").split(',') if m)
            to_remove = set(m.strip() for m in msg.get("REMOVE", "").split(',') if m)
            group['members'].update(to_add)
            group['members'].difference_update(to_remove)
            print(f"\nThe group “{group['group_name']}” member list was updated.")
            print(f"> ", end="", flush=True)

def handle_group_message(msg, args):
    group_id = msg.get("GROUP_ID")
    if group_id in state.groups and args.id in state.groups[group_id]['members']:
        from_id = msg.get("FROM")
        content = msg.get("CONTENT")
        display = state.peers.get(from_id, (from_id,))[0]
        print(f"\n[{state.groups[group_id]['group_name']}] {display}: {content}")
        print(f"> ", end="", flush=True)
