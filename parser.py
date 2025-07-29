def build_message(fields):
    """builds a LSNP message from a dict of fields"""
    return ''.join(f"{k}: {v}\n" for k, v in fields.items()) + "\n"

def parse_message(raw):
    """parse raw LSNP message into a dict"""
    lines = raw.strip().split('\n')
    msg = {}
    for line in lines:
        if ':' not in line:
            continue
        k, v = line.split(':', 1)
        msg[k.strip()] = v.strip()
    return msg
