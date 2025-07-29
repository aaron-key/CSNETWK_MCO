import time

verbose_mode = False

def set_verbose(flag):
    global verbose_mode
    verbose_mode = flag

def log(message, direction="INFO"):
    if verbose_mode:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"[{ts}] {direction} > {message}")
