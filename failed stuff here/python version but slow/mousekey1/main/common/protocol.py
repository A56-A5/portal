# common/protocol.py
import json

def encode_event(event: dict) -> bytes:
    return json.dumps(event).encode('utf-8')

def decode_event(data: bytes) -> dict:
    return json.loads(data.decode('utf-8'))
