# 🌙 LateNight Music Selfbot

A Discord selfbot that plays music through your own user account via Lavalink v4 + FluxWave. Built for personal use.

> [!WARNING]
> **⚠️ EXPERIMENTAL — USE AT YOUR OWN RISK**
> Selfbots violate [Discord's Terms of Service](https://discord.com/terms). Using this may result in your account being **permanently banned**. By using this project, you acknowledge the risk. **yup-console (iworship.ayush) is not responsible for any action taken against your account.**

---

## Requirements

- Python 3.11+
- A Discord user account token
- A running Lavalink v4 node (a public one is pre-configured)

---

## Installation

**1. Clone the repo**
```bash
git clone https://github.com/yup-console/latenight-selfbot
cd latenight-selfbot
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

`requirements.txt`:
```
discord.py-self>=2.1.0
fluxwave>=0.1.1
aiohttp>=3.9.0
```

**3. Configure `latenight.py`**

Open the file and edit the config section at the top:

```python
OWNER_IDS = {
    901487880067776524,   # your Discord user ID
    # 123456789012345678, # add more trusted users here
}

TOKEN = "YOUR_DISCORD_TOKEN_HERE"
```

**4. Run**
```bash
python latenight.py
```

You should see:
```
[INFO] latenight: [start] Starting LateNight Music Selfbot by yup-console...
[INFO] latenight: [ready] Logged in as YourName#0000
[INFO] latenight: [ready] Music cog loaded.
```

---

## Configuration

| Variable | Description |
|---|---|
| `OWNER_IDS` | Set of Discord user IDs allowed to use commands |
| `TOKEN` | Your Discord account token |
| `PREFIX` | Command prefix (default: `>`) |
| `LAVALINK_HOST` | Lavalink server host |
| `LAVALINK_PORT` | Lavalink server port |
| `LAVALINK_PASS` | Lavalink server password |

The bot works in **any channel** — there is no channel restriction.

---

## Commands

All commands use the `>` prefix.

### 🛠️ Utility
| Command | Description |
|---|---|
| `>help` / `>mh` | Show all commands |
| `>ping` | Show bot latency |
| `>uptime` | Show how long the bot has been running |
| `>node` | Show Lavalink node status |

### 🎵 Playback
| Command | Aliases | Description |
|---|---|---|
| `>play <query/url>` | `>p` | Play a song or add it to the queue. Supports YouTube, SoundCloud, and direct URLs |
| `>playnext <query>` | `>pn` | Add a track to the front of the queue (plays next) |
| `>skip` | `>s`, `>next` | Skip the current track |
| `>stop` | — | Stop playback and clear the queue |
| `>pause` | — | Pause the current track |
| `>resume` | `>unpause` | Resume a paused track |
| `>seek <position>` | — | Seek to a position, e.g. `>seek 1:30` or `>seek 90` |

### 📋 Queue
| Command | Aliases | Description |
|---|---|---|
| `>queue` | `>q` | Show the current queue with progress bar |
| `>nowplaying` | `>np` | Show what's currently playing |
| `>shuffle` | — | Shuffle the queue |
| `>loop <mode>` | — | Set loop mode: `track`, `queue`, or `off` |
| `>remove <#>` | — | Remove a track by position, e.g. `>remove 3` |
| `>clear` | — | Clear the queue without stopping playback |

### 🔊 Audio Filters
| Command | Aliases | Description |
|---|---|---|
| `>volume <0-200>` | `>vol` | Set volume (default 100) |
| `>nightcore` | `>nc` | Apply nightcore filter (pitch + speed up) |
| `>bassboost` | `>bb` | Apply bass boost filter |
| `>vaporwave` | `>vw` | Apply vaporwave filter (slowed + reverb feel) |
| `>resetfilter` | `>rf`, `>clearfilter` | Remove all active filters |

### 🔗 Connection
| Command | Aliases | Description |
|---|---|---|
| `>join` | `>j` | Join your current voice channel |
| `>disconnect` | `>dc`, `>leave` | Disconnect from voice channel |

---

## Multiple Owners

You can allow multiple Discord accounts to use the bot by adding their user IDs to `OWNER_IDS`:

```python
OWNER_IDS = {
    901487880067776524,   # main account
    123456789012345678,   # friend's account
    987654321098765432,   # another account
}
```

---

## Lavalink

The bot comes pre-configured with a public Lavalink node. If it goes down, you can self-host one or replace it in the config:

```python
LAVALINK_HOST = "your.lavalink.host"
LAVALINK_PORT = 2333
LAVALINK_PASS = "youshallnotpass"
LAVALINK_SECURE = False  # True if using HTTPS/WSS
```

---

## Disclaimer

This project is for **experimental and educational purposes only**. Usage of selfbots is against Discord's Terms of Service. The author **yup-console (iworship.ayush)** holds no liability for any consequences including but not limited to account termination, bans, or data loss resulting from use of this software. **You use this entirely at your own risk.**

---

<p align="center">Made with 🌙 by <b>yup-console</b></p>
