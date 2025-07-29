import argparse
from network import create_socket, receive_loop, send_message
from parser import parse_message, build_message
from parser import build_message
import uuid
import time
import state
import utils

print(">> Starting LSNP peer...")

def handle_message(raw, addr):
    msg = parse_message(raw)
    msg_type = msg.get("TYPE", "UNKNOWN")
    utils.log(f"RECV < {addr[0]} [{msg_type}]", "RECV")
    
    if msg_type == "PROFILE":
        user_id = msg.get("USER_ID")
        display = msg.get("DISPLAY_NAME", user_id)
        status = msg.get("STATUS", "")
        state.peers[user_id] = (display, status)
        print(f"[PROFILE] {display} — {status}")
    
    elif msg_type == "POST":
        user_id = msg.get("USER_ID")
        content = msg.get("CONTENT", "")
        state.posts.append((user_id, content))
        display = state.peers.get(user_id, (user_id,))[0]
        print(f"[POST] {display}: {content}")

    elif msg_type == "DM":
        from_id = msg.get("FROM")
        to_id = msg.get("TO")
        content = msg.get("CONTENT", "")
        state.dms.append((from_id, to_id, content))
        display = state.peers.get(from_id, (from_id,))[0]
        print(f"[DM] {display} to you: {content}")

    elif msg_type == "FOLLOW":
        from_id = msg.get("FROM")
        display = state.peers.get(from_id, (from_id,))[0]
        print(f"User {display} has followed you")

    elif msg_type == "UNFOLLOW":
        from_id = msg.get("FROM")
        display = state.peers.get(from_id, (from_id,))[0]
        print(f"User {display} has unfollowed you")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true', help='Enable verbose mode')
    parser.add_argument('--name', required=True, help='Your display name')
    parser.add_argument('--id', required=True, help='Your user ID in format user@ip')
    args = parser.parse_args()

    utils.set_verbose(args.verbose)
    sock = create_socket()
    profile_fields = {
        "TYPE": "PROFILE",
        "USER_ID": args.id,
        "DISPLAY_NAME": args.name,
        "STATUS": "Exploring LSNP!",
    }
    send_message(sock, build_message(profile_fields), '<broadcast>', args.verbose)
    receive_loop(sock, handle_message, verbose=args.verbose)

    print("[LSNP] Peer is running. Type 'post <msg>' or 'dm <to> <msg>' or 'quit'")
    while True:
        try:
            cmd = input("> ").strip()
            if cmd.startswith("post "):
                content = cmd[5:]
                fields = {
                    "TYPE": "POST",
                    "USER_ID": args.id,
                    "CONTENT": content,
                    "TTL": 3600,
                    "MESSAGE_ID": "msgid123",
                    "TOKEN": f"{args.id}|9999999999|broadcast"
                }
                send_message(sock, build_message(fields), '<broadcast>', args.verbose)
            elif cmd.startswith("dm "):
                parts = cmd.split(' ', 2)
                if len(parts) == 3:
                    to_id, content = parts[1], parts[2]
                    fields = {
                        "TYPE": "DM",
                        "FROM": args.id,
                        "TO": to_id,
                        "CONTENT": content,
                        "TIMESTAMP": "999999999",
                        "MESSAGE_ID": "msgid456",
                        "TOKEN": f"{args.id}|9999999999|chat"
                    }
                    ip = to_id.split('@')[1]
                    send_message(sock, build_message(fields), ip, args.verbose)
            elif cmd == "quit":
                break
            elif cmd.startswith("follow "):
                to_id = cmd.split(' ')[1]
                fields = {
                    "TYPE": "FOLLOW",
                    "MESSAGE_ID": uuid.uuid4().hex[:8],
                    "FROM": args.id,
                    "TO": to_id,
                    "TIMESTAMP": str(int(time.time())),
                    "TOKEN": f"{args.id}|9999999999|follow"
                }
                ip = to_id.split('@')[1]
                send_message(sock, build_message(fields), ip, args.verbose)

            elif cmd.startswith("unfollow "):
                to_id = cmd.split(' ')[1]
                fields = {
                    "TYPE": "UNFOLLOW",
                    "MESSAGE_ID": uuid.uuid4().hex[:8],
                    "FROM": args.id,
                    "TO": to_id,
                    "TIMESTAMP": str(int(time.time())),
                    "TOKEN": f"{args.id}|9999999999|follow"
                }
                ip = to_id.split('@')[1]
                send_message(sock, build_message(fields), ip, args.verbose)

            elif cmd == "peers":
                for uid, (name, status) in state.peers.items():
                    print(f"{name} ({uid}) — {status}")
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()
