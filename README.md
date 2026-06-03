# Koda

A terminal-based cinema client for the Kodik streaming database.
Search titles, browse your library, stream via mpv, and download episodes — all from the keyboard.

---

## Features

- Full-text search across movies, series, and anime from the Kodik catalogue
- Season, episode, and dubbing selection with persistent progress tracking
- **Auto-advance** to the next episode after playback (5-second countdown, press `S` to skip)
- Library with custom and system folders (Favourites, Continue Watching, Downloaded)
  - Full-text search within any folder
  - Folder reordering via `Alt+↑` / `Alt+↓`
  - Episode progress indicator on each item
- Episode download via ffmpeg with **per-episode real-time progress**
  - **Pause / resume** downloading at any time
  - System desktop notification on completion
- Token verification before saving settings
- Background update checker against GitHub Releases
- Hotkey reference popup (`?`) available on any screen
- **oscc** subtitle integration for mpv (auto-detected)
- Portable single-file build for Windows, macOS, and Linux — no Python required

---

## Requirements

| Dependency | Purpose | Required |
|------------|---------|----------|
| Python 3.12+ | Runtime (source only) | Yes |
| [mpv](https://mpv.io/installation/) | Video playback | Yes |
| [ffmpeg](https://ffmpeg.org/download.html) | Episode download | Optional |
| Kodik API token | Content access | Yes |

---

## Installation

### Portable build (recommended)

Download the binary for your platform from the [latest release](https://github.com/SnapD3v/koda/releases/latest):

| Platform | File |
|----------|------|
| Windows  | `koda.exe` |
| macOS    | `koda-macos` |
| Linux    | `koda-linux` |

On macOS / Linux, make it executable first:
```
chmod +x koda-macos && ./koda-macos
```

On first launch, open **Settings** (`Ctrl+,`) and enter your Kodik API token.

### From source

```
git clone https://github.com/SnapD3v/koda.git
cd koda
pip install -e .
koda
```

---

## Configuration

Settings are saved to `~/.config/koda/config.toml` and can be edited via the built-in Settings screen.

| Key | Default | Description |
|-----|---------|-------------|
| `token` | — | Kodik API token |
| `player` | `mpv` | Player executable name or path |
| `quality` | `720` | Preferred stream quality (360 / 480 / 720 / 1080) |
| `downloads_dir` | `~/Downloads/Koda` | Download destination |

---

## Keybindings

Press `?` anywhere to open the full hotkey reference. Key highlights:

### Global
| Key | Action |
|-----|--------|
| `?` | Hotkey reference |
| `Ctrl+Q` | Quit |
| `Ctrl+L` | Library |

### Home screen
| Key | Action |
|-----|--------|
| `S` | Search |
| `L` | Library |
| `Ctrl+,` | Settings |
| `U` | Updates |

### Search
| Key | Action |
|-----|--------|
| `Escape` | Back |

### Detail (title card)
| Key | Action |
|-----|--------|
| `P` | Play |
| `S` | Cancel auto-advance to next episode |
| `Escape` | Back |

### Library
| Key | Action |
|-----|--------|
| `N` | New folder |
| `D` | Delete selected |
| `Alt+↑` / `Alt+↓` | Reorder folders |
| `Escape` | Back / exit folder |

---

## Building from source

Install [PyInstaller](https://pyinstaller.org) and run:

```
pip install pyinstaller
pyinstaller koda.spec --clean --noconfirm
```

Output: `dist/koda.exe` (Windows), `dist/koda` (macOS / Linux).

### Bundling mpv (Windows portable only)

To ship a self-contained Windows build with mpv included:

1. Download the [mpv Windows portable](https://sourceforge.net/projects/mpv-player-windows/) and extract to `bundled/mpv/`
2. Optionally place `oscc.lua` in `bundled/mpv/scripts/`
3. Run `pyinstaller koda.spec --clean --noconfirm`

The spec file detects `bundled/mpv/` automatically and includes it in the build.

### Releasing a new version

1. Bump `version` in `pyproject.toml` and `koda/__init__.py`
2. Commit and tag:
   ```
   git commit -m "chore: release vX.Y.Z"
   git tag vX.Y.Z
   git push origin master --tags
   ```
3. GitHub Actions builds binaries for Windows, macOS, and Linux and publishes a GitHub Release automatically.

---

## License

MIT
