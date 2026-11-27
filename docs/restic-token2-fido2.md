# Encrypting restic backups with a Token2 FIDO2 security key

**Goal:** make backup data that can be decrypted **only with a physical Token2 key** — requiring both
the key's **PIN** and a **touch**. The encryption password is stored nowhere; the key *computes* it on demand.

## About restic

restic is a fast, modern, open-source backup program and one of the most trusted tools of its kind.
It **encrypts everything client-side** with AES-256 by default, **deduplicates** data so backups stay
compact, and verifies integrity with content hashes — so corruption is detected, not silently restored.
It runs on Linux, Windows and macOS, writes to many storage backends (local, SFTP, REST server, S3,
Backblaze B2, Azure, Google Cloud and more), and has been independently audited. Simple, secure, dependable.

restic protects a repository with a password. The only question this guide answers: **where do you keep
that password?** On disk, a stolen machine gives it away. We make a **Token2** FIDO2 key produce it instead.

## How it works

The FIDO2 **hmac-secret** extension turns a Token2 key into a deterministic secret generator: for a fixed
*credential* + *salt*, the key always returns the **same 32-byte secret** — but only after **PIN + touch**,
and only from **that physical key**. That secret becomes the restic repository password, so it exists
**nowhere on disk**. No key → the backups are unreadable ciphertext.

> Tested with Token2 FIDO2.1 keys that support **hmac-secret** and have a **PIN set** (PIN+ / Molto2 /
> T2F2). Set a PIN first with `fido2-token -S <device>` if needed.

## Prerequisites (Linux)

```bash
sudo apt install fido2-tools restic openssl
fido2-token -L        # list keys → note the device, e.g. /dev/hidraw0 ($DEV below)
```

## Step 1 — Enroll the key (once)

```bash
DEV=$(fido2-token -L | head -1 | cut -d: -f1)
sudo install -d -m 700 /etc/restic-fido2

printf '%s\n%s\n%s\n%s\n' \
  "$(head -c32 /dev/urandom | base64)" "restic-backup" "restic" "$(head -c16 /dev/urandom | base64)" \
  | fido2-cred -M -h -v "$DEV" | fido2-cred -V -h -o /tmp/cred.out
#            ^ -h hmac-secret   ^ -v user verification (PIN)   (PIN + touch prompted now)

sudo sed -n 1p /tmp/cred.out | sudo tee /etc/restic-fido2/credential >/dev/null
head -c32 /dev/urandom | base64 | sudo tee /etc/restic-fido2/salt    >/dev/null
sudo rm -f /tmp/cred.out; sudo chmod 600 /etc/restic-fido2/*
```

Back up `/etc/restic-fido2` and enroll a **second Token2 key** too — credentials can't be copied between
keys, so losing the only key means losing access.

## Step 2 — Password helper

```bash
sudo tee /usr/local/bin/restic-fido2-pass.sh >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
DIR=/etc/restic-fido2
DEV=$(fido2-token -L | head -1 | cut -d: -f1)
printf '%s\n%s\n%s\n%s\n' \
  "$(head -c32 /dev/urandom | base64)" "restic-backup" \
  "$(cat "$DIR/credential")" "$(cat "$DIR/salt")" \
  | fido2-assert -G -h -v "$DEV" | tail -n1
EOF
sudo chmod 700 /usr/local/bin/restic-fido2-pass.sh
```

Run it **twice** — with PIN + touch each time it prints the **same** string (stable secret). restic reads
it with `--password-command`.

## Step 3 — Verify: encrypt & decrypt a file with the key

```bash
echo "Token2 secret $(date)" | sudo tee /tmp/plain.txt

# encrypt (PIN + touch) — secret piped in, never on the command line
sudo /usr/local/bin/restic-fido2-pass.sh \
  | sudo openssl enc -aes-256-cbc -pbkdf2 -salt -pass stdin -in /tmp/plain.txt -out /tmp/cipher.bin
sudo od -A x -t x1z /tmp/cipher.bin | head -3   # unreadable ciphertext

# decrypt (PIN + touch again → same secret)
sudo /usr/local/bin/restic-fido2-pass.sh \
  | sudo openssl enc -d -aes-256-cbc -pbkdf2 -pass stdin -in /tmp/cipher.bin -out /tmp/decrypted.txt
sudo cat /tmp/decrypted.txt               # original text is back

# a wrong password cannot open it:
echo wrong-password \
  | sudo openssl enc -d -aes-256-cbc -pbkdf2 -pass stdin -in /tmp/cipher.bin -out /dev/null   # "bad decrypt"
```

Point restic at the same helper — `restic --password-command /usr/local/bin/restic-fido2-pass.sh …` —
and every `init` / `backup` / `restore` is gated by the Token2 key.

## Notes & caveats

- **Set a PIN on the key** (`fido2-token -S $DEV`) — user verification depends on it.
- **Keep user verification consistent:** always use `-v`; the hmac-secret differs with/without PIN.
- **Enroll a backup key** and store it safely; credentials can't be copied between keys.
- `/dev/hidrawN` can change; the helper re-detects it. Community integration — verify on your Token2 model.
