# Encrypting restic backups with a Token2 FIDO2 security key

**Goal:** protect data so it can be decrypted **only with a physical Token2 key** — requiring both
the key's **PIN** and a **touch**. The password is stored nowhere; the key *computes* it on demand.

restic encrypts its repository with a password — but *where do you keep that password?* On disk, a
stolen machine gives it away. This guide uses the FIDO2 **hmac-secret** extension of a Token2 key as a
deterministic secret generator: for a fixed *credential* + *salt* the key always returns the **same
32-byte secret** — but only after **PIN + touch**, and only from **that physical key**. That secret
becomes the repository password, so it exists **nowhere on disk**. No key → the backups are unreadable
ciphertext.

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

Run it **twice** — with PIN + touch each time it prints the **same** string (stable secret):

```bash
sudo /usr/local/bin/restic-fido2-pass.sh
sudo /usr/local/bin/restic-fido2-pass.sh
```

## Step 3 — Verify: encrypt & decrypt a file with the key

```bash
echo "Bitrone secret $(date)" | sudo tee /tmp/plain.txt

# encrypt (PIN + touch) — secret piped in, never on the command line
sudo /usr/local/bin/restic-fido2-pass.sh \
  | sudo openssl enc -aes-256-cbc -pbkdf2 -salt -pass stdin -in /tmp/plain.txt -out /tmp/cipher.bin
sudo xxd /tmp/cipher.bin | head -2        # unreadable ciphertext

# decrypt (PIN + touch again → same secret)
sudo /usr/local/bin/restic-fido2-pass.sh \
  | sudo openssl enc -d -aes-256-cbc -pbkdf2 -pass stdin -in /tmp/cipher.bin -out /tmp/decrypted.txt
sudo cat /tmp/decrypted.txt               # original text is back

# a wrong password cannot open it:
echo wrong-password \
  | sudo openssl enc -d -aes-256-cbc -pbkdf2 -pass stdin -in /tmp/cipher.bin -out /dev/null   # "bad decrypt"
```

## Step 4 — Use it with restic

```bash
export RESTIC_REPOSITORY=/srv/backups/myrepo
restic --password-command /usr/local/bin/restic-fido2-pass.sh init
restic --password-command /usr/local/bin/restic-fido2-pass.sh backup /data
restic --password-command /usr/local/bin/restic-fido2-pass.sh restore latest --target /restore
```

Every call asks for **PIN + touch**; without the key restic cannot open the repository.

## Notes & caveats

- **Set a PIN on the key** (`fido2-token -S $DEV`) — user verification depends on it.
- **Keep user verification consistent:** always use `-v`; the hmac-secret differs with/without PIN.
- **Enroll a backup key** and store it safely; credentials can't be copied between keys.
- `/dev/hidrawN` can change; the helper re-detects it. Unofficial integration — verify on your Token2 model.

## References

- libfido2 manuals — <https://developers.yubico.com/libfido2/Manuals/fido2-assert.html>
- libfido2 examples — <https://cgit.freebsd.org/src/plain/contrib/libfido2/examples/README.adoc>
- hmac-secret CLI gist — <https://gist.github.com/joostd/ef34e52d17bbf546977ff8cfd61f38cd>
- Token2 integration guides — <https://www.token2.com/pages/integration-guides>
