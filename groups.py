import time
import state
from network import send_message
from parser import build_message

# --- handling group cmds ---
def process_creategroup(cmd, sock, args):
    # processes "creategroup" cmd
    try:
        # split the cmd by parts
        _, group_id, group_name, members_str = cmd.split(' ', 3)

        # split the member string
        initial_members = set(m.strip() for m in members_str.split(','))
        initial_members.add(args.id)    # add creator as part of the members

        # store group information locally
        state.groups[group_id] = {
            "group_name": group_name,
            "members": initial_members,
            "creator": args.id
        }

        # prepare GROUP_CREATE msg
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

        # send GROUP_CREATE msg to all members part of the group
        for member_id in initial_members:
            ip = member_id.split('@')[1]
            send_message(sock, msg, ip, args.verbose)

        # print group creation success
        print(f"Group '{group_name}' created and invites sent.")
    except ValueError:
        print("Usage: creategroup <id> <name> <member1>,<member2>,...")

def process_updategroup(cmd, sock, args):
    # processes "addtogroup" and "removefromgroup" cmds
    try: 
        # split the cmd by parts
        action, group_id, members_str = cmd.split(' ', 2)

        # check if group exists and user is the creator of the group
        if group_id in state.groups and state.groups[group_id]['creator'] == args.id:
            # split the member string
            members_to_act = set(m.strip() for m in members_str.split(','))

            # prepare GROUP_UPDATE msg
            fields = {
                "TYPE": "GROUP_UPDATE", 
                "FROM": args.id, 
                "GROUP_ID": group_id,
                "TIMESTAMP": str(int(time.time())), "TOKEN": f"{args.id}|9999999999|group"
            }

            # set ADD / REMOVE fields
            if "add" in action:
                fields["ADD"] = ",".join(members_to_act)
            else:
                fields["REMOVE"] = ",".join(members_to_act)
            message = build_message(fields)

            # create list of recipients of the msg
            current_members = state.groups[group_id]['members']
            all_recipients = current_members.union(members_to_act)

            # send GROUP_UPDATE to group members and members added / removed
            for member_id in all_recipients:
                ip = member_id.split('@')[1]
                send_message(sock, message, ip, args.verbose)

            # print group update success
            print(f"Group update sent for '{state.groups[group_id]['group_name']}'.")
        else:
            print("Error: Group not found or you are not the creator.")
    except ValueError:
        print("Usage: addtogroup <group_id> <user1>,<user2> OR removefromgroup <group_id> <user1>")

def process_gmsg(cmd, sock, args):
    # processes "gmsg" cmd
    try:
        # split the cmd by parts
        _, group_id, content = cmd.split(' ', 2)

        # check if group exists and user is part of the group
        if group_id in state.groups and args.id in state.groups[group_id]['members']:
            # prepare GROUP_MESSAGE msg
            fields = {
                "TYPE": "GROUP_MESSAGE", 
                "FROM": args.id, 
                "GROUP_ID": group_id,
                "CONTENT": content, 
                "TIMESTAMP": str(int(time.time())),
                "TOKEN": f"{args.id}|9999999999|group"
            }
            message = build_message(fields)

            # send GROUP_MESSAGE to group members
            for member_id in state.groups[group_id]['members']:
                ip = member_id.split('@')[1]
                send_message(sock, message, ip, args.verbose)
        else:
            print("Error: You are not a member of that group or the group does not exist.")
    except ValueError:
        print("Usage: gmsg <group_id> <message>")

def process_listgroups(args):
    # processes "listgroups" cmd
    print("--- your groups ---")
    found = False

    # list all group info
    for group_id, group_data in state.groups.items():
        if args.id in group_data['members']:
            found = True
            print(f"- {group_data['group_name']} ({group_id})")
            print(f"  Creator: {group_data['creator']}")
            print(f"  Members: {', '.join(group_data['members'])}")

    # if no groups were found
    if not found:
        print("You are not a member of any groups.")
    print("-----------------------")

# --- handling group messages
def handle_group_create(msg, args):
    # handles GROUP_CREATE msg
    group_id = msg.get("GROUP_ID")
    members_str = msg.get("MEMBERS", "")
    members = set(m.strip() for m in members_str.split(','))

    # if user was found in the list of members
    if args.id in members:
        # add new group to list of groups
        state.groups[group_id] = {
            "group_name": msg.get("GROUP_NAME"),
            "members": members,
            "creator": msg.get("FROM")
        }

        # if user was not the creator of the group
        if msg.get("FROM") != args.id:
            print(f"\nYou've been added to group '{msg.get('GROUP_NAME')}' ({group_id}).")
            print(f"> ", end="", flush=True)

def handle_group_update(msg):
    # handles GROUP_UPDATE msgs
    group_id = msg.get("GROUP_ID")

    # if group is found (aka user is member of the group)
    if group_id in state.groups:
        group = state.groups[group_id]

        # if msg originates from the groups creator (only creator can edit groups)
        if msg.get("FROM") == group['creator']:
            # retrieve list of members to add / remove
            to_add = set(m.strip() for m in msg.get("ADD", "").split(',') if m)
            to_remove = set(m.strip() for m in msg.get("REMOVE", "").split(',') if m)

            # add / remove members depending on msg action (ADD / REMOVE)
            group['members'].update(to_add)
            group['members'].difference_update(to_remove)
            print(f"\nThe group “{group['group_name']}” member list was updated.")
            print(f"> ", end="", flush=True)

def handle_group_message(msg, args):
    # handles GROUP_MESSAGE msgs
    group_id = msg.get("GROUP_ID")
    
    # if group is found and user is member of the group
    if group_id in state.groups and args.id in state.groups[group_id]['members']:
        # display group name, members, and msg
        from_id = msg.get("FROM")
        content = msg.get("CONTENT")
        display = state.peers.get(from_id, (from_id,))[0]
        print(f"\n[{state.groups[group_id]['group_name']}] {display}: {content}")
        print(f"> ", end="", flush=True)
