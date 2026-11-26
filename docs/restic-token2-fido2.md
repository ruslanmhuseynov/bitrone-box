# Encrypting restic backups with a Token2 FIDO2 security key

**Goal:** make a [restic](https://restic.net) backup repository that can only be
**decrypted / restored with a physical Token2 FIDO2 key** — requiring both the key's
**PIN** and a **touch**. Deleting or reading the backups is impossible without the key.

> restic has **no native FIDO2 support** — it opens a repository with a password or a
> key file. So we make the Token2 key *produce* that password. Two approaches are shown:
> **Method A (hmac‑secret)** — the key *is* the key (recommended, cryptographic);
> **Method B (pam_u2f)** — the key *authorizes* the operation (simpler, a gate).

Tested with Token2 FIDO2.1 keys that support the **hmac‑secret** extension and have a
**PIN set** (e.g. PIN+ / Molto2 / T2F2 series). Set a PIN on the key first with
`fido2-token -S <device>` if you have not already.

---

## Prerequisites (Linux)

```bash
sudo apt install fido2-tools restic          # Debian/Ubuntu
fido2-token -L                               # list keys → note the device, e.g. /dev/hidraw0
```

Keep the device path handy; below it is referenced as `$DEV`.

---

## Method A — the key derives the repository password (hmac‑secret)

The FIDO2 **hmac‑secret** extension turns the key into a deterministic secret generator:
for a fixed *credential* + *salt*, the key returns the **same 32‑byte secret** every time —
but only after **PIN + touch**, and only from **that physical key**. We use that secret as
the restic repository password via `--password-command`.

Because the secret depends on whether **user verification (PIN)** was performed, we always
request it (`-v`). This is what makes PIN mandatory — and keeps the secret stable.

### 1. Enroll the key (once)

```bash
DEV=$(fido2-token -L | head -1 | cut -d: -f1)      # e.g. /dev/hidraw0
sudo install -d -m 700 /etc/restic-fido2
RP="restic-backup"                                  # relying-party id (any stable string)

# create a credential WITH hmac-secret, requiring user verification (PIN)
printf '%s\n%s\n%s\n%s\n' \
  "$(head -c32 /dev/urandom | base64)" "$RP" "restic" "$(head -c16 /dev/urandom | base64)" \
  | fido2-cred -M -h -v "$DEV" | fido2-cred -V -h -o /tmp/cred.out
#            ^ -h = hmac-secret   ^ -v = user verification (PIN)   (touch + PIN prompted now)

sudo sed -n 1p /tmp/cred.out | sudo tee /etc/restic-fido2/credential >/dev/null   # credential id
head -c32 /dev/urandom | base64 | sudo tee /etc/restic-fido2/salt      >/dev/null  # fixed salt
sudo rm -f /tmp/cred.out
sudo chmod 600 /etc/restic-fido2/*
```

> Keep `credential` and `salt` safe (and backed up): with them **and the key** you can
> reproduce the password; without the **key** they are useless. Losing the key = losing
> access, so enroll a **second Token2 key** too (repeat with its own files) and use it as
> the password for a second copy of the repo, or store a sealed emergency password offline.

### 2. Password helper

`/usr/local/bin/restic-fido2-pass.sh`:

```bash
#!/usr/bin/env bash
# Prints the restic repo password derived from the Token2 key (PIN + touch required).
set -euo pipefail
DIR=/etc/restic-fido2
DEV=$(fido2-token -L | head -1 | cut -d: -f1)
printf '%s\n%s\n%s\n%s\n' \
  "$(head -c32 /dev/urandom | base64)" "restic-backup" \
  "$(cat "$DIR/credential")" "$(cat "$DIR/salt")" \
  | fido2-assert -G -h -v "$DEV" | tail -n1      # last line = 32-byte hmac secret (base64)
```

```bash
sudo install -m 700 restic-fido2-pass.sh /usr/local/bin/restic-fido2-pass.sh
```

### 3. Create / use the repository

```bash
export RESTIC_REPOSITORY=/srv/backups/myrepo         # or rest:…, s3:…, sftp:… etc.
restic --password-command /usr/local/bin/restic-fido2-pass.sh init          # creates repo
restic --password-command /usr/local/bin/restic-fido2-pass.sh backup /data  # backup
restic --password-command /usr/local/bin/restic-fido2-pass.sh restore latest --target /restore
```

Each call asks for **PIN**, then a **touch**. No key → `restic` cannot open the repository.

---

## Method B — the key authorizes the operation (pam_u2f gate)

Simpler: the repository keeps a normal password, and a **Token2 key (PIN + touch)** is
required to *run* the restore/decrypt command. Good as a second factor and against casual
access; note a root user on the host can bypass it, and the password still exists on disk.

### 1. Enroll

```bash
sudo apt install libpam-u2f pamtester
sudo pamu2fcfg -o pam://restic -i pam://restic | sudo tee /etc/restic-u2f_keys
sudo chmod 600 /etc/restic-u2f_keys       # touch (+ PIN) during enrollment
```

### 2. PAM service `/etc/pam.d/restic-restore` — **require PIN + touch**

```
auth  required  pam_u2f.so authfile=/etc/restic-u2f_keys origin=pam://restic appid=pam://restic cue pinverification=1
auth  required  pam_permit.so
```

`pinverification=1` forces PIN; `cue` prompts the touch.

### 3. Gate your restore script

```bash
pamtester restic-restore "$USER" authenticate || { echo "key not confirmed"; exit 1; }
restic -r "$REPO" restore latest --target /restore
```

---

## Token2 notes & caveats

- **Set a PIN on the key** (`fido2-token -S $DEV`) — Method A's user verification and the
  `pinverification=1` option both depend on it.
- **Keep user verification consistent** in Method A: always use `-v`. The hmac‑secret
  differs between a PIN‑verified and a non‑verified assertion, so mixing them changes the
  derived password.
- **Enroll a backup key.** FIDO2 credentials cannot be copied between keys — register a
  second Token2 key and keep it in a safe. Losing the only key means losing access.
- **Device path** (`/dev/hidrawN`) can change; the helper re‑detects it with
  `fido2-token -L`. For multiple keys, select by product string.
- This is unofficial, community integration (restic has no built‑in FIDO2); verify on your
  exact Token2 model before relying on it in production.

---

### References

- libfido2 `fido2-assert` / `fido2-cred` manuals — <https://developers.yubico.com/libfido2/Manuals/fido2-assert.html>
- libfido2 examples (`assert.c`, README) — <https://cgit.freebsd.org/src/plain/contrib/libfido2/examples/README.adoc>
- hmac‑secret CLI walkthrough (community gist) — <https://gist.github.com/joostd/ef34e52d17bbf546977ff8cfd61f38cd>
- Token2 integration guides — <https://www.token2.com/pages/integration-guides>
