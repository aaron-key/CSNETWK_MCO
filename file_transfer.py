import os
import base64
import mimetypes
import uuid
import time
import threading
import state
import utils
from network import send_message
from parser import build_message

CHUNK_DATA_SIZE = 1024

def assemble_and_save_file(file_id, sock, args):
    if file_id not in state.incoming_files:
        return
    
    file_info = state.incoming_files[file_id]
    metadata = file_info('metadata')
    filename = metadata['FILENAME']

    # place files in a separate "downloads" folder
    download_dir = 'downloads'
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    filepath = os.path.join(download_dir, filename)

    # sort chunks by index and combine
    try: 
        with open(filepath, 'wb') as f:
            sorted_chunks = sorted(file_info['received_chunks'].items())
            for index, chunk_data in sorted_chunks:
                f.write(chunk_data)

            # indicate file transfer complete
            print(f"\nFile transfer of '{filename}' is complete. Saved to {filepath}")

            # send a FILE_RECEIVED confirmation back to sender
            receipt_fields = {
                "TYPE": "FILE_RECEIVED",
                "FROM": args.id,
                "TO": metadata['FROM'],
                "FILEID": file_id,
                "STATUS": "COMPLETE",
                "TIMESTAMP": str(int(time.time()))
            }
            ip = metadata['FROM'].split('@')[1]
            send_message(sock, build_message(receipt_fields), ip, args.verbose)

    except Exception as e:
        print(f"\n[ERROR] Could not save file {filename}: {e}")
    finally:
        # clean up state for file tranfer
        del state.incoming_files[file_id]
        print(f"> ", end="", flush=True)

def initiate_file_transfer(sock, from_id, to_id, filepath, verbose):
    if not os.path.exists(filepath):
        print(f"[ERROR] File not found: {filepath}")
        return
    
    # preparing file metadata
    filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)
    filetype, _ = mimetypes.guess_type(filepath)
    if filetype is None:
        filetype = 'application/octet-stream'
    file_id = uuid.uuid4().hex[:8]

    # send FILE_OFFER
    offer_fields = {
        "TYPE": "FILE_OFFER", 
        "FROM": from_id, 
        "TO": to_id,
        "FILENAME": filename, 
        "FILESIZE": filesize, 
        "FILETYPE": filetype,
        "FILEID": file_id, 
        "DESCRIPTION": "Oh look a file",
        "TIMESTAMP": str(int(time.time())),
        "TOKEN": f"{from_id}|{int(time.time()) + 3600}|file"
    }
    ip = to_id.split('@')[1]
    send_message(sock, build_message(offer_fields), ip, verbose)
    print(f"Send file offer for '{filename}' to {to_id}.")

    # read the file and send in chunks
    try:
        with open(filepath, 'rb') as f:
            total_chunks = (filesize + CHUNK_DATA_SIZE - 1)
            chunk_index = 0
            while True:
                chunk_data = f.read(CHUNK_DATA_SIZE)
                if not chunk_data:
                    break       # end of file

                chunk_fields = {
                    "TYPE": "FILE_CHUNK", 
                    "FROM": from_id, 
                    "TO": to_id,
                    "FILEID": file_id, 
                    "CHUNK_INDEX": chunk_index,
                    "TOTAL_CHUNKS": total_chunks,
                    "CHUNK_SIZE": len(chunk_data),
                    "TOKEN": f"{from_id}|{int(time.time()) + 3600}|file",
                    "DATA": base64.b64encode(chunk_data).decode('utf-8')
                }
                send_message(sock, build_message(chunk_fields), ip, verbose)
                chunk_index += 1
                time.sleep(0.01)
        utils.log(f"Finished sending all {total_chunks} chunks for file {file_id}.", "SEND")
    except Exception as e:
        print(f"[ERROR] Failed to send file: {e}")

# --- handling incoming file-related messages

def handle_file_offer(msg):
    file_id = msg.get("FILEID")
    from_id = msg.get("FROM")
    filename = msg.get("FILENAME")
    filesize = msg.get("FILESIZE")

    state.file_offers[file_id] = msg
    display = state.peers.get(from_id, (from_id))[0]

    # prompt user to accept file
    print(f"\nUser {display} is sending you a file: '{filename}' ({filesize} bytes).")
    print(f"To accept, type: accept {file_id}")
    print(f"> ", end="", flush=True) 

def handle_file_chunk(msg, sock, args):
    file_id = msg.get("FILEID")
    if file_id in state.incoming_files:
        file_info = state.incoming_files[file_id]
        total_chunks = int(msg.get("TOTAL_CHUNKS"))
        file_info['total_chunks'] = total_chunks
        chunk_index = int(msg.get("CHUNK_INDEX"))
        data = base64.b64decode(msg.get("DATA"))

        if chunk_index not in file_info['received_chunks']:
            file_info['received_chunks'][chunk_index] = data

        if len(file_info['received_chunks']) == total_chunks:
            assemble_and_save_file(file_id, sock, args)

def handle_file_received(msg):
    from_id = msg.get("FROM")
    status = msg.get("STATUS")
    file_id = msg.get("FILEID")
    display = state.peers.get(from_id, (from_id))[0]
    utils.log(f"User {display} confirmed 'status' for file {file_id}", "INFO")

# --- handling user commands

def process_sendfile(cmd, sock, args):
    try:
        _, to_id, filepath = cmd.split(' ', 2)
        threading.Thread(target = initiate_file_transfer, args = (sock, args.id, to_id, filepath, args.verbose), daemon = True).start()
    except ValueError:
        print("Usage: sendfile <user_id> <path_to_file>")

def process_accept(cmd):
    try:
        _, file_id_to_accept = cmd.split(' ', 1)
        if file_id_to_accept in state.file_offers:
            offer = state.file_offers.pop(file_id_to_accept)
            state.incoming_files[file_id_to_accept] = {
                'metadata': offer,
                'received_chunks': {},
                'total_chunks': 0
            }
            print(f"Accepted file trasnfer for '{offer['FILENAME']}'. Waiting for chunks...")
        else:
            print("Invalid or expired file offer ID.")
    except ValueError:
        print("Usage: accept <file_id>")