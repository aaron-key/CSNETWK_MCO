import socket
import threading

UDP_PORT = 50999
BUFFER_SIZE = 65535

def create_socket():
    """creates and bind udp socket for broadcast"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(('', UDP_PORT))  # bind to all interfaces
    return sock

def receive_loop(sock, handler, verbose=False):
    """listens for incoming messages and calls the handler"""
    def loop():
        while True:
            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
                message = data.decode('utf-8')
                handler(message, addr)
            except Exception as e:
                if verbose:
                    print(f"[ERROR] Failed to receive message: {e}")
    threading.Thread(target=loop, daemon=True).start()

def send_message(sock, message, ip, verbose=False):
    sock.sendto(message.encode('utf-8'), (ip, UDP_PORT))
    if verbose:
        dest_type = "BROADCAST" if ip == "<broadcast>" else "UNICAST"
        print(f"SEND > ({dest_type}) {ip}:{UDP_PORT}\n{message}")

