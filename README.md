# ClashBotAI (Template Matching + EasyOCR)

ClashBotAI is a Clash of Clans farming bot for Python 3.11 that uses:

- ADB (BlueStacks on `localhost:5555`) for device control
- OpenCV template matching for UI/button detection
- EasyOCR for resource number reading
- A state machine for bot flow orchestration

## Demo Overlay

Example live preview overlay (regions + template/debug annotations):

![ClashBotAI live overlay demo](docs/demo-overlay.png)

## Current Runtime Behavior

- Uses template matching for:
  - Home `Attack!`
  - Find Match / Army Attack
  - Next Match
  - Return Home
  - Wall and wall-upgrade buttons
- Uses OCR for home/enemy gold and elixir values
- Wall upgrade checks are only evaluated after a completed battle cycle
- Wall upgrade threshold uses OR logic:
  - `home_gold >= 10,000,000` **OR** `home_elixir >= 10,000,000`

---

## Requirements

The bot is Python plus ADB. You need:

- **Python 3.11** (Windows, Linux, or macOS)
- **ADB** (`adb` on your PATH)
- An Android emulator or device with Clash of Clans (README examples use BlueStacks on `localhost:5555`; any setup that answers `adb devices` is fine)

Install Python dependencies:

```bash
python3 -m pip install --user -r requirements.txt
```

Install **ADB** (pick your OS):

- **macOS** (Homebrew): `brew install android-platform-tools`
- **Windows**: install [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools) and add the folder containing `adb.exe` to your PATH, or use a package manager such as [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/) / Chocolatey / Scoop if you already use one for `adb`
- **Linux** (Debian/Ubuntu): `sudo apt install android-tools-adb` (package name may vary by distro)

---

## Quick Start

From project root (use your actual clone path on Windows/Linux/macOS):

```bash
cd path/to/clashbotAI
adb connect localhost:5555
adb devices
```

### Dry run (no taps/swipes sent)

```bash
python3 main.py --dry-run --preview --preview-scale 0.8 --debug-dir debug --debug-every 2
```

### Live run (real taps/swipes)

```bash
python3 main.py --preview --preview-scale 0.8 --debug-dir debug --debug-every 2
```

Stop bot:

- Press `q` or `Esc` in preview window, or
- Press `Ctrl+C` in terminal

---

## Building a standalone executable (optional)

The project is normally run with `python3 main.py`. For a packaged app, use [PyInstaller](https://pyinstaller.org/) with the checked-in spec (bundles `config.yaml`, `templates/`, EasyOCR, and PyTorch):

```bash
python3 -m pip install pyinstaller
pyinstaller --noconfirm clashbotai.spec
```

Output is `dist/clashbotai/` with `clashbotai` or `clashbotai.exe` plus DLLs and data files. **`--noconfirm`** overwrites a previous `dist/` build.

**Important:** Defaults load `config.yaml` and template paths from the **current working directory** (or set `BOT_CONFIG_PATH`). Run the executable **from the project root**, or keep `config.yaml` and `templates/` next to the built folder as laid out under `dist/clashbotai/`.

### Pre-built Windows `.exe` (GitHub Actions)

This repo includes a workflow that builds on **Windows** and uploads **`ClashBotAI-windows-amd64.zip`** (the whole `dist/clashbotai` folder, including `clashbotai.exe`).

1. Create and push a [semantic version tag](https://semver.org/) (example `v0.1.0`):

   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

2. In GitHub, open the **Actions** tab and wait for **Windows executable** to finish.

3. Open **[Releases](https://github.com/picklesauce/clashbotAI/releases)** and download **`ClashBotAI-windows-amd64.zip`** for that tag.

To try a build without tagging, run **Windows executable** via **Actions → Windows executable → Run workflow**; download the **artifact** zip from the run summary (not attached to a Release).

Unzip on Windows, install ADB on your PATH, connect your emulator (`adb connect ...`), then run **`clashbotai.exe`** from inside the extracted `clashbotai` folder. First OCR run may download EasyOCR model files into your user profile.

### Manual PyInstaller (without the spec)

**macOS / Linux** (`:` separates source and destination for `--add-data`):

```bash
python3 -m pip install pyinstaller
pyinstaller --onedir --name clashbotai \
  --add-data "config.yaml:." \
  --add-data "templates:templates" \
  main.py
```

**Windows** (use `;` instead of `:` in `--add-data`):

```powershell
pyinstaller --onedir --name clashbotai `
  --add-data "config.yaml;." `
  --add-data "templates;templates" `
  main.py
```

If imports fail, prefer **`clashbotai.spec`** (above), which pulls EasyOCR and Torch explicitly.

---

## Project Files

- `main.py` - main loop, preview/debug output, execution
- `state_machine.py` - bot decision logic and state transitions
- `adb_controller.py` - all ADB actions (tap/swipe/screenshot/readiness)
- `template_matcher.py` - OpenCV template matching engine
- `ocr.py` - EasyOCR reading + OCR stabilization
- `config.yaml` - thresholds, regions, template paths, coordinates
- `templates/` - image templates used by matcher
- `debug/` - saved overlay snapshots + `events.jsonl`

---

## Config Notes

Primary knobs in `config.yaml`:

- `thresholds.upgrade_min_resource`
- `thresholds.match_min_gold`
- `thresholds.match_min_elixir`
- `thresholds.require_both_for_wall_upgrade`
- `templates.thresholds.*` (per-template confidence tuning)
- `templates.regions.*` (search areas)
- `regions.*` (OCR crop regions)
- `coordinates.*` (fallback tap points)

---

## Troubleshooting

### `adb: command not found`

Install platform-tools for your OS (see **Requirements**), then open a **new** terminal so `PATH` is refreshed.

### Bot taps unexpectedly after reconnect

Stop any old bot process, then reconnect ADB. On **macOS or Linux** you can use:

```bash
pkill -f "main.py" || true
adb disconnect
adb connect localhost:5555
```

On **Windows**, end the stuck Python or `clashbotai` process from Task Manager (or `Stop-Process` in PowerShell if you know the process name), then run the same `adb disconnect` / `adb connect` lines in **Command Prompt** or PowerShell.

### OCR wrong / unstable

- Tune `regions.home_*` and `regions.enemy_*` in `config.yaml`
- Check overlay output with `--preview`
- Inspect `debug/events.jsonl` for OCR values and actions

### Template not detected

- Replace template image in `templates/`
- Tune `templates.thresholds.<key>`
- Narrow or widen `templates.regions.<key>`

---

## Safety

Start with dry-run before live mode after any template/config change.
