# PhotoBackup Verifier

Guarantees your backup drive is a **100% perfect mirror** of your source drive using SHA-256 checksums — no guessing based on file names or dates. Built for photographers who need certainty their shoots are fully backed up before wiping cards.

## Install (one command)

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/youbethemoose/photoverifier/main/install.sh)
```

Or clone and run locally:

```bash
git clone https://github.com/youbethemoose/photoverifier.git
cd photoverifier
bash install.sh
```

The installer will:
- Install Homebrew if you don't have it
- Install Python 3.13 + tkinter
- Build `PhotoVerifier.app` on your Desktop, ready to double-click

> **macOS only.** Tested on macOS Sequoia 15.

---

## How to use

### Step 1 — Scan & Compare
Select your **source** (internal drive or card) and **backup drive**, then click **Scan & Compare**. Every file on both drives gets SHA-256 hashed and compared.

### Step 2 — Sync to Backup
Copies only the files that are missing or have a hash mismatch. Files already identical are skipped — no wasted transfer time.

### Step 3 — Full Verify
Re-scans **both drives from scratch** and recomputes every hash. Only passes when every single file matches byte-for-byte. Use this after syncing to get 100% confirmation.

---

## Summary cards

| Card | Meaning |
|---|---|
| ✓ Identical | Already on backup, byte-perfect |
| → Missing on backup | Need to copy |
| ! Content differs | Same filename, different bytes — will be re-copied |
| ← Only on backup | On backup but not in source |

---

## Speed

Speed is limited by your slowest drive's read speed:

| Drive | ~Speed | 50 GB shoot |
|---|---|---|
| NVMe internal | 3–5 GB/s | ~15 sec |
| Thunderbolt SSD | 1–2 GB/s | ~1 min |
| USB-C SSD | 400–900 MB/s | 2–4 min |
| USB 3.0 HDD | 100–150 MB/s | 8–15 min |

---

## Requirements

- macOS 12 Ventura or later
- Homebrew (installer will set it up if missing)
- Internet connection for first install only
