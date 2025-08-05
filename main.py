import argparse
import threading
from network import create_socket, receive_loop, send_message
from parser import parse_message, build_message
import uuid
import time
import state
import utils
import file_transfer
import tictactoe
import groups

print(">> Starting LSNP peer...")

def send_ping(sock, user_id, verbose):
    # sends a ping message every 5 mins
    while True:
        time.sleep(300)
        utils.log("Sending periodic PING", "SEND")
        ping_fields = {
            "TYPE": "PING",
            "USER_ID": user_id
        }
        send_message(sock, build_message(ping_fields), "<broadcast>", verbose)

def handle_message(raw, addr, sock, args):
    msg = parse_message(raw)
    msg_type = msg.get("TYPE", "UNKNOWN")

    # do not process own broadcast msgs
    sender_id = msg.get("USER_ID") or msg.get("FROM")
    if sender_id == args.id:
        if args.verbose:
            utils.log(f"RECV < self [{msg_type}]", "RECV")
        return

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
        timestamp = msg.get("TIMESTAMP")
        if user_id and timestamp:
            post_key = (user_id, timestamp)
            if post_key not in state.posts:
                state.posts[post_key] = {
                    'content': content,
                    'likes': set()
                }
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

    elif msg_type == "LIKE":
        from_id = msg.get("FROM")
        to_id = msg.get("TO")
        post_timestamp = msg.get("POST_TIMESTAMP")
        action = msg.get("ACTION")
        post_key = (to_id, post_timestamp)

        if post_key in state.posts:
            post = state.posts[post_key]
            if action == "LIKE":
                post['likes'].add(from_id)
            elif action == "UNLIKE":
                post['likes'].discard(from_id)

        if to_id == args.id:
                liker_display = state.peers.get(from_id, (from_id,))[0]
                action_text = "likes" if action == "LIKE" else "unlikes"
                print(f"\n{liker_display} {action_text} your post '{post['content'][:30]}...'")
                print(f"> ", end="", flush=True)

    # --- group-related messages
    elif msg_type == "GROUP_CREATE":
        groups.handle_group_create(msg, args)
    elif msg_type == "GROUP_UPDATE":
        groups.handle_group_update(msg)
    elif msg_type == "GROUP_MESSAGE":
        groups.handle_group_message(msg, args)

    # --- tictactoe-related messages
    elif msg_type == "TICTACTOE_INVITE":
        tictactoe.handle_invite(msg)
    elif msg_type == "TICTACTOE_MOVE":
        tictactoe.handle_move(msg)
    elif msg_type == "TICTACTOE_RESULT":
        tictactoe.handle_result(msg)

    # --- file-related messages
    elif msg_type == "FILE_OFFER":
        file_transfer.handle_file_offer(msg)
    elif msg_type == "FILE_CHUNK":
        file_transfer.handle_file_chunk(msg, sock, args)
    elif msg_type == "FILE_RECEIVED":
        file_transfer.handle_file_received(msg)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true', help='Enable verbose mode')
    parser.add_argument('--name', required=True, help='Your display name')
    parser.add_argument('--id', required=True, help='Your user ID in format user@ip')
    args = parser.parse_args()

    utils.set_verbose(args.verbose)
    sock = create_socket()

    handler = lambda raw, addr: handle_message(raw, addr, sock, args)
    receive_loop(sock, handler, verbose=args.verbose)

    # send ping periodically every 5mins
    ping_thread = threading.Thread(target = send_ping, args = (sock, args.id, args.verbose), daemon = True)
    ping_thread.start()

    profile_fields = {
        "TYPE": "PROFILE",
        "USER_ID": args.id,
        "DISPLAY_NAME": args.name,
        "STATUS": "Exploring LSNP!",
    }
    send_message(sock, build_message(profile_fields), '<broadcast>', args.verbose)

    print("[LSNP] Peer is running. Type 'post <msg>' or 'dm <to> <msg>' or 'quit'")
    while True:
        try:
            cmd = input("> ").strip()
            if cmd.startswith("post "):
                content = cmd[5:]
                timestamp = str(int(time.time()))
                post_key = (args.id, timestamp)
                state.posts[post_key] = {
                    'content': content,
                    'likes': set()
                }
                fields = {
                    "TYPE": "POST",
                    "USER_ID": args.id,
                    "CONTENT": content,
                    "TTL": 3600,
                    "MESSAGE_ID": "msgid123",
                    "TOKEN": f"{args.id}|{timestamp}|broadcast"
                }
                send_message(sock, build_message(fields), '<broadcast>', args.verbose)

            elif cmd == "ping":
                ping_fields = {
                    "TYPE": "PING",
                    "USER_ID": args.id
                }
                send_message(sock, build_message(ping_fields), "<broadcast>", args.verbose)

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

            # --- follow / unfollow commands
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

            # --- group commands
            elif cmd.startswith("creategroup "):
                groups.process_creategroup(cmd, sock, args)
            elif cmd.startswith("addtogroup ") or cmd.startswith("removefromgroup "):
                groups.process_updategroup(cmd, sock, args)
            elif cmd.startswith("gmsg "):
                groups.process_gmsg(cmd, sock, args)
            elif cmd == "listgroups":
                groups.process_listgroups(args)

            # --- tictactoe commands
            elif cmd.startswith("ttt "):
                try:
                    _, opponent_id = cmd.split(' ', 1)
                    tictactoe.initiate_game(sock, args.id, opponent_id, args.verbose)
                except ValueError:
                    print("Usage: ttt <user.id")
            elif cmd.startswith("move "):
                tictactoe.process_move(cmd, sock, args)

            # --- file commands
            elif cmd.startswith("sendfile "):
                file_transfer.process_sendfile(cmd, sock, args)
            elif cmd.startswith("accept "):
                file_transfer.process_accept(cmd)
                
            # --- liking posts
            elif cmd.startswith("timeline"):
                print("--- recent posts ---")
                sorted_posts = sorted(state.posts.items(), key = lambda item: int(item[0][1]), reverse = True)
                state.timeline_cache = sorted_posts
                if not sorted_posts:
                    print("No posts to show.")
                for i, (post_key, post_data) in enumerate(sorted_posts):
                    author_id, _ = post_key
                    author_display = state.peers.get(author_id, (author_id,))[0]
                    like_count = len(post_data['likes'])
                    print(f"[{i}] {author_display}: {post_data['content']} ({like_count} likes)")
                print("---------------------")
            elif cmd.startswith("like ") or cmd.startswith("unlike "):
                parts = cmd.split(' ')
                action = "LIKE" if parts[0] == "like" else "UNLIKE"
                try:
                    index = int(parts[1])
                    if 0 <= index < len(state.timeline_cache):
                        post_key, _ = state.timeline_cache[index]
                        to_id, post_timestamp = post_key
                        fields = {
                            "TYPE": "LIKE",
                            "FROM": args.id,
                            "TO": to_id,
                            "POST_TIMESTAMP": post_timestamp,
                            "ACTION": action,
                            "TIMESTAMP": str(int(time.time())),
                            "TOKEN": f"{args.id}|9999999999|broadcast"
                        }
                        send_message(sock, build_message(fields), '<broadcast>', args.verbose)
                        print(f"Send {action} for post {index}")
                    else:
                        print("Invalid post index.")
                except (ValueError, IndexError):
                    print(f"Usage: {action.lower()} <post_index")

            elif cmd == "peers":
                for uid, (name, status) in state.peers.items():
                    print(f"{name} ({uid}) — {status}")

            elif cmd == "quit":
                break

            elif cmd == "help":
                print("Available commands:\n"
                      "  post <message>          - Post a public message.\n"
                      "  ping                    - Sends a broadcast ping .\n"
                      "  dm <user> <message>     - Sends a private message to a user.\n"
                      "  timeline                - View recent posts.\n"
                      "  like <index>            - Like a post from the timeline.\n"
                      "  unlike <index>          - Unlike a post from the timeline.\n"
                      "  sendfile <user> <path>  - Offer to send a file to a user.\n"
                      "  accept <file_id>        - Accept a file offer.\n"
                      "  creategroup <id> <name> <members> - Create a group.\n"
                      "  addtogroup <id> <members>   - Add members to a group you own.\n"
                      "  removefromgroup <id> <members> - Remove members from a group.\n"
                      "  gmsg <id> <message>       - Send a message to a group.\n"
                      "  listgroups              - List the groups you are in.\n"
                      "  ttt <user>              - Invite a user to play Tic-Tac-Toe.\n"
                      "  move <game_id> <pos>    - Make a move in a Tic-Tac-Toe game.\n"
                      "  peers                   - List all known peers.\n"
                      "  quit                    - Exit the application.")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
