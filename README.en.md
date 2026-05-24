# 📸 Daily Album — Synology Photos

> A Python script that automatically creates a photo album on your Synology NAS every morning,
> picking memories based on the theme of the day: anniversary photos from the same date,
> seasonal photos, or a random selection from your entire library.

---

## 🗓️ How it works day to day

Every morning at the time you choose, the NAS runs the script automatically. The script
connects to Synology Photos, selects around thirty photos based on the day's theme
(one day it shows memories from exactly 1, 2, 5 or 10 years ago; another day photos
from the same month across all years; another day a random draw from the full library),
then updates an existing album by replacing yesterday's photos with today's.
The album stays in the same place with the same invited people — only the photos change.
You don't have to do anything: you open Synology Photos in the morning and the new photos are there.

---

## ✅ Requirements

| What you need | Why |
|---|---|
| **Synology NAS with DSM 7.2 or later** | DSM is the NAS operating system. Version 7.2 brings the Photos API the script needs. |
| **Synology Photos app installed** | This is the photo management app on the NAS, available for free in Package Center. |
| **Python 3.9 or later** | Python is the language the script is written in. Install it from Package Center (package named "Python 3"). |
| **Two user accounts on the NAS** | `your_user`: your personal account for SSH and installation. `script_user`: a dedicated account the script uses to access the Photos API. The `script_user` account must have access to the Synology Photos shared space. |

---

## 🖥️ Installation on the Synology NAS

This section walks through every step from your Windows PC to the first automated run.

---

### Step A — Enable SSH in DSM

SSH lets you send commands to the NAS from your PC, as if you had a keyboard plugged into it.

**In DSM:**

1. Click **Control Panel** (toolbox icon on the DSM desktop)
2. In the left sidebar, click **Terminal & SNMP**

   > 📺 *You see a page with two tabs: "Terminal" and "SNMP". You're in the right place.*

3. Check the box **Enable SSH service**
4. Leave the port at **22** (that's the standard value)
5. Click **Apply**

   > 📺 *A confirmation message briefly appears at the bottom of the screen. SSH is now active.*

---

### Step B — Install PuTTY and connect via SSH from Windows

**Download and install PuTTY** (SSH client for Windows):
[https://www.putty.org](https://www.putty.org) → "Download PuTTY" button

> PowerShell has a built-in SSH client, but it can run into algorithm compatibility issues
> with some Synology NAS devices. PuTTY is more reliable.

**Open PuTTY** and configure the connection:
- Host Name: `192.168.X.X` (replace with your NAS IP address)
- Port: `22`
- Connection type: `SSH`
- Click **Open**

> 📺 *The first time, PuTTY shows a security alert about the server key.
> Click "Accept". A black window opens and asks for your username.*

Enter your username (`your_user`) then your password
(characters don't appear on screen — that's normal).

You're connected when you see a line like:
```
your_user@DiskStation:~$
```

> You can find the NAS IP in DSM → Control Panel → Network → General.

---

### Step C — Copy the project to the NAS

> **Important note about paths:** The DSM File Station interface shows shortened paths,
> different from the actual paths used in SSH. The mapping is:
>
> | What you see in File Station | What you type in SSH |
> |---|---|
> | `home/download/MyFolder` | `/volume1/homes/YOUR_USER/download/MyFolder` |
> | `home/Job/MyFolder` | `/volume1/homes/YOUR_USER/Job/MyFolder` |
>
> In practice: replace `home/` with `/volume1/homes/YOUR_USER/` to get the SSH path.

**On your Windows PC**, open a PowerShell window (Windows key → "PowerShell") and type:

```powershell
scp -r "C:\Users\YOUR_USERNAME\Claude\Album" your_user@192.168.X.X:/volume1/homes/YOUR_USER/download/AlbumPhotoAuto
```

Adjust `C:\Users\YOUR_USERNAME\Claude\Album` to the folder where the project is on your PC,
and `192.168.X.X` to your NAS IP address.

> 📺 *PowerShell displays files as they are copied, with their sizes.
> When done, the command returns to the prompt with no error message.*

---

### Step D — Run the installation script

**In the PuTTY window connected to the NAS** (the one showing `your_user@DiskStation:~$`):

```bash
cd /volume1/homes/YOUR_USER/download/AlbumPhotoAuto
bash scripts/install_on_dsm.sh
```

> 📺 *The script displays its progress with green checkmarks (✓). It creates the directory
> `/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/`, installs Python in an isolated environment,
> and copies all the necessary files. At the end, it shows a summary of commands to use.*

If you want a different installation directory, you can specify it:

```bash
bash scripts/install_on_dsm.sh /volume2/my-scripts/album
```

---

### Step E — Fill in the configuration file

The installation script has created a blank `config.yml` file to fill in.
Open it with the built-in text editor:

```bash
nano /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml

> (In File Station, this folder is visible as `home/Job/AlbumPhotoAuto/`)
```

> 📺 *The nano editor opens in the terminal. Arrow keys move the cursor.
> When you're done, press `Ctrl+X`, then `Y` (yes to save), then `Enter`.*

> **Note about accounts:** There are two distinct accounts on the NAS.
> - `your_user`: your personal account, used for SSH and installation.
> - `script_user`: the dedicated account used by the script to access the Synology Photos API.
> These two things are separate. Here you fill in the credentials for the `script_user` account.

Fill in **at minimum** these four lines:

```yaml
synology:
  host: "http://192.168.X.X"      # ← your NAS IP address
  port: 5000
  username: "script_user"          # ← the dedicated script account (≠ your SSH account your_user)
  password: "your_password"        # ← the script_user account password
```

See the **Configuration** section below for details on all settings.

---

### Step F — Test without changing anything

```bash
/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/.venv/bin/python \
  /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/main.py \
  --config /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml \
  --dry-run --debug
```

> 📺 *The terminal shows each action the script WOULD have taken, without touching the NAS.
> The last line should display "SIMULATION COMPLETE" with the number of photos selected.
> If you see "ERROR", read the message: it tells you exactly what's wrong
> (wrong password, incorrect IP, etc.).*

---

### Step G — First real run

When the simulation test went well, run for real:

```bash
/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/.venv/bin/python \
  /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/main.py \
  --config /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml \
  --debug
```

Albums appear in Synology Photos (Albums section). Go share them
manually with the people of your choice (see Step H).

---

### Step H — Configure album sharing (one-time setup)

1. Open **Synology Photos** in your browser
2. Go to the **Albums** section in the left menu

   > 📺 *You see the created albums: "Daily Album — Anniversaries", "Daily Album — Season", "Daily Album — Random". Some may be missing if that day's theme hasn't run yet — that's normal.*

3. For **each album**, right-click on it → **Share**
   (or click the three dots `⋯` that appear on hover)
4. In the sharing window:
   - Click **Invite users**
   - Type the account name to invite, select it
   - Set the role to **Viewer**
   - Click **Save**

The script never touches sharing settings. Invited users remain from one day to the next.

---

### Step I — Set up the scheduled task in DSM

This is what makes the script run automatically every morning.

1. In DSM, click **Control Panel**
2. Click **Task Scheduler**

   > 📺 *A window opens with the task list (it may be empty). The toolbar
   > at the top offers: Create / Edit / Delete / Run.*

3. Click **Create → Scheduled Task → User-defined script**

   > 📺 *A window with three tabs opens: General / Schedule / Task Settings.*

4. **General tab**:
   - Task name: `Daily Album`
   - User: select the `your_user` account
   - Leave "Enabled" checked

5. **Schedule tab**:
   - Run: `Daily`
   - Time: `06:00` (or the time of your choice)
   - Repeat: unchecked (once a day is enough)

6. **Task Settings tab**:
   - In the **Run command** field, paste exactly:

   ```
   /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/.venv/bin/python /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/main.py --config /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml
   ```

   > 📺 *This is a single line, no line break. If you installed in a different
   > directory, adjust the paths accordingly.*

   - In **Send run details by email**, you can enter your address
     if you want to be notified in case of an error.

7. Click **OK**

---

### Step J — Test with "Run Now"

To verify the scheduled task works correctly without waiting until tomorrow morning:

1. In **Task Scheduler**, click on the `Daily Album` task to select it
2. Click **Run** in the toolbar

   > 📺 *A dialog box asks for confirmation. Click Yes. The task runs
   > in the background — no window opens, that's normal.*

3. Wait 30 seconds to 2 minutes depending on the size of your library
4. Go to Synology Photos → Albums: the album photos have changed

To see the detailed execution result:
- In Task Scheduler, click the task → **Results**
- The "Information" column shows whether the task succeeded or failed

---

### Step K — Where to find logs in case of problems

The script writes a detailed log at this location:

```
/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/logs/album.log
```

**To read it from SSH:**
```bash
tail -50 /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/logs/album.log
```
(shows the last 50 lines — those from the last run)

**To read it from DSM:**
Open **File Station**, navigate to `/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/logs/`,
double-click `album.log`.

An error line looks like:
```
2026-05-15 06:00:12 | ERROR    | Authentication error: ...
```
The text after the colon explains the cause.

---

## ⚙️ Configuration — what to put in `config.yml`

Here is the file explained line by line. Lines starting with `#` are comments ignored by the script.

```yaml
synology:
  host: "http://192.168.X.X"      # Your NAS IP address on the local network
  port: 5000                       # 5000 = standard connection, 5001 = encrypted (HTTPS)
  username: "script_user"          # The dedicated account that creates the albums (≠ your SSH account your_user)
  password: "your_password"        # Its password — NEVER share this file

album:
  name_prefix: "Daily Album"       # The beginning of each album name (followed by the theme)
  photo_count: 30                  # Number of photos in each album

cache:
  max_age_hours: 24                # The script re-lists all photos every 24h
  force_refresh: false             # Set to true to force a full re-read on next run

themes:
  rotation: "anniversary,season,random"    # Theme rotation order
  anniversary_years_back: "1,2,3,5,10"    # Years back for the anniversary theme
  # exclude_paths: "19*,VHS*,Archives"     # Folders to never include (* are wildcards)
  no_repeat_days_anniversary: 30           # An anniversary photo doesn't reappear for 30 days
  no_repeat_days_season: 30               # Same for the season theme
  no_repeat_days_random: 30               # Same for the random theme (0 = disabled)

logs:
  retention_days: 30               # Number of days of logs to keep
  level: "INFO"                    # INFO = normal | DEBUG = very detailed (for debugging)
```

### Themes in detail

| Name | What it does |
|---|---|
| `anniversary` | Photos taken around the same calendar date (± a few days) in previous years. E.g.: on May 15, it looks for photos from May 15, 2024, 2022, 2020, 2015… |
| `season` | Photos taken during the same month as today, across all years. In May → photos from every May. |
| `random` | Random draw from the entire library. |

The value `rotation: "anniversary,season,random"` means themes rotate in that order, day after day. With 3 themes: day 1 → anniversary, day 2 → season, day 3 → random, day 4 → anniversary, etc.

### Avoiding photo repetition

By default, a photo that has already appeared in an album won't reappear for **30 days** for that same theme. This window is configurable independently for each theme:

```yaml
themes:
  no_repeat_days_anniversary: 30   # "quarantine" days for the anniversary theme
  no_repeat_days_season: 30        # same for season
  no_repeat_days_random: 30        # same for random
```

**Configuration examples:**

| Case | Setting |
|---|---|
| Library of fewer than 500 photos → risk of running out | Reduce to `14` or `7` |
| Large library, no repetition for 2 months | Set to `60` |
| Completely disable for a theme | Set to `0` |

**What happens if all photos are in quarantine** (library too small): the script ignores the no-repeat constraint for that run and picks photos anyway. A warning is written to the logs.

History is stored in `cache/history.json`. It is purged automatically — only entries within the largest configured window are kept.

---

### Excluding folders

If you have folders you never want to appear in the albums (VHS scans, work archives, etc.):

```yaml
  exclude_paths: "VHS*,19*,Work,Family/Archives"
```

- `VHS*` → all folders whose name starts with `VHS`
- `19*` → all folders whose name starts with `19` (e.g. `1994`, `1998`)
- `Work` → exactly the folder named `Work`
- `Family/Archives` → the `Archives` subfolder inside `Family`

After modifying this list, re-run with `--rebuild-index` to rebuild the photo list:

```bash
/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/.venv/bin/python \
  /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/main.py \
  --config /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml \
  --rebuild-index --dry-run
```

---

## 🔄 Changing frequency or themes

### Changing the run time

In DSM → **Task Scheduler**, double-click the `Daily Album` task, **Schedule** tab, change the time.

### Enabling or disabling a theme

In `config.yml`, modify the `rotation` line. For example, to have only random albums:

```yaml
  rotation: "random"
```

To alternate only anniversaries and season:

```yaml
  rotation: "anniversary,season"
```

### Forcing a theme manually (for testing)

```bash
PYTHON=/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/.venv/bin/python
MAIN=/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/main.py
CONFIG=/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml

$PYTHON $MAIN --config $CONFIG --theme random
$PYTHON $MAIN --config $CONFIG --theme anniversary
$PYTHON $MAIN --config $CONFIG --theme season
```

---

## 🔍 Troubleshooting — if the album isn't updated in the morning

### 1. Check the logs

```bash
tail -50 /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/logs/album.log
```

### 2. Re-run manually in verbose mode

```bash
/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/.venv/bin/python \
  /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/main.py \
  --config /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml \
  --debug
```

An `ERROR` or `WARNING` message shows where things went wrong.

### 3. Test the connection without changing anything

```bash
/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/.venv/bin/python \
  /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/main.py \
  --config /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml \
  --dry-run --debug
```

### 4. Rebuild the photo list

If the script says the index is empty or no photos are found:

```bash
/volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/.venv/bin/python \
  /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/main.py \
  --config /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml \
  --rebuild-index --debug
```

### 5. Common problems

| Symptom | Likely cause | Solution |
|---|---|---|
| `Authentication error` | Wrong username or password | Check `username` and `password` in `config.yml` |
| `Index is empty` | The account doesn't have access to the shared space | In Synology Photos → Settings → Shared Space → Permissions, add the `script_user` account |
| `Configuration error` | `config.yml` incorrectly filled or missing | Check the file exists and all sections are present |
| Albums no longer shared | The album was deleted and manually recreated | Reconfigure sharing in Synology Photos (see Step H) |
| No photos for the anniversary theme | No photos taken around this date in past years | Normal: the script automatically falls back to random theme |
| Photos repeat despite no-repeat setting | Library too small for the configured window | Reduce `no_repeat_days_*` in `config.yml`, or check the log (`All photos in the pool are in history`) |
| Scheduled task doesn't run | Wrong user selected | Check that the user in Task Scheduler has rights to the script directory |

---

## ⚠️ Known limitations

- **Album sharing must be configured manually.** The Synology Photos API doesn't allow adding invited users via a script — this must be done once in the web interface.

- **Photos without an EXIF date are ignored by the anniversary theme.** Files without metadata only appear in the random theme.

- **The anniversary theme may find nothing.** If no photos were taken around the current date in previous years, the script automatically falls back to the random theme.

- **One album per theme.** If the script runs twice on the same day, it simply replaces the photos — no duplicates.

- **The photo index is cached for 24h.** If you add new photos to the NAS, re-run with `--rebuild-index` to include them immediately.

---

## 📋 FOR THE USER

### Validation checklist — check in order

```
INSTALLATION
  [ ] A. SSH enabled in DSM (Control Panel → Terminal & SNMP)
  [ ] B. PuTTY installed, SSH connection tested successfully
           PuTTY → Host: 192.168.X.X, Port: 22 → connected as your_user
  [ ] C. Project copied to NAS with scp (from PowerShell on PC)
           scp -r "C:\...\Album" your_user@NAS_IP:/volume1/homes/YOUR_USER/download/AlbumPhotoAuto
  [ ] D. Installation script run without red errors (from PuTTY on NAS)
           cd /volume1/homes/YOUR_USER/download/AlbumPhotoAuto
           bash scripts/install_on_dsm.sh
  [ ] E. config.yml filled with the NAS IP, account, and password

TESTING
  [ ] F. Simulation OK (no errors, photos selected)
           ... main.py --dry-run --debug
  [ ] G. First real run OK (albums visible in Synology Photos)
           ... main.py --debug
  [ ] H. Albums shared manually in Synology Photos
           (Albums → ⋯ → Share → Invite → Viewer)
           Daily Album — Anniversaries  [ ]
           Daily Album — Season         [ ]
           Daily Album — Random         [ ]

AUTOMATION
  [ ] I. Scheduled task created in DSM (Task Scheduler)
           User    : your_user
           Time    : 06:00
           Command : /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/.venv/bin/python
                     /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/main.py
                     --config /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/config.yml
  [ ] J. "Run Now" tested → album updated in Synology Photos
  [ ] K. Logs checked (no ERROR lines)
           /volume1/homes/YOUR_USER/Job/AlbumPhotoAuto/logs/album.log
```

```
┌──────────────────────────────────────────────────────────────┐
│                      ONE-PAGE SUMMARY                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  FILE TO NEVER SHARE: config.yml                             │
│  (contains your NAS password)                                │
│                                                              │
│  WHAT RUNS AUTOMATICALLY (don't touch):                      │
│  → Script runs every morning at 06:00                        │
│  → It replaces photos in the existing albums                 │
│  → If an album doesn't exist yet, it creates it              │
│                                                              │
│  WHAT IS DONE ONLY ONCE (manually):                          │
│  → Configure who sees each album in Synology Photos          │
│    (Albums → ⋯ → Share → Invite → Viewer)                   │
│                                                              │
│  IF SOMETHING DOESN'T WORK:                                  │
│  1. Read: logs/album.log (last lines)                        │
│  2. SSH to the NAS and re-run with --debug                   │
│  3. Task results in DSM Task Scheduler                       │
│                                                              │
│  TEST WITHOUT CHANGING ANYTHING:                             │
│  → main.py --dry-run --debug                                 │
│                                                              │
│  FORCE A THEME:                                              │
│  → main.py --theme random                                    │
│  → main.py --theme anniversary                               │
│  → main.py --theme season                                    │
│                                                              │
│  ALBUMS (names in Synology Photos):                          │
│  → "Daily Album — Anniversaries"                             │
│  → "Daily Album — Season"                                    │
│  → "Daily Album — Random"                                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```
