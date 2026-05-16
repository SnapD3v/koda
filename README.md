# Koda

A terminal-based cinema client for the Kodik streaming database.
Search titles, browse your library, stream via mpv, and download episodes — all from the keyboard.

---

## Features

- Full-text search across movies, series, and anime from the Kodik catalogue
- Season, episode, and dubbing selection with persistent progress tracking
- Library with custom and system folders (Favourites, Continue Watching, Downloaded)
- Episode download via ffmpeg with real-time progress
- Settings screen: API token, player, quality, download directory
- Update checker against GitHub Releases
- Portable single-file Windows build — no Python required

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

Download `koda.exe` from the [latest release](https://github.com/SnapD3v/koda/releases/latest) and run it directly. No Python or additional setup needed.

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

The token can also be set via environment variable `KODIK_TOKEN` or a `.env` file in the working directory.

---

## Keybindings

### Global
| Key | Action |
|-----|--------|
| `Ctrl+Q` | Quit |
| `Ctrl+L` | Library |

### Home screen
| Key | Action |
|-----|--------|
| `S` | Search |
| `L` | Library |
| `Ctrl+,` | Settings |
| `U` | Updates |

### Search / Library / Detail
| Key | Action |
|-----|--------|
| `Escape` | Back |
| `P` | Play (Detail screen) |
| `N` | New folder (Library) |
| `D` | Delete selected (Library) |

---

## Building from source

Install [PyInstaller](https://pyinstaller.org) and run:

```
pip install pyinstaller
pyinstaller koda.spec --clean --noconfirm
```

Output: `dist/koda.exe`

### Releasing a new version

1. Bump `version` in `pyproject.toml` and `__version__` in `koda/__init__.py`
2. Commit and tag:
   ```
   git commit -m "chore: release vX.Y.Z"
   git tag vX.Y.Z
   git push origin master --tags
   ```
3. GitHub Actions builds `koda.exe` and publishes a GitHub Release automatically.

---

## Dependencies note

ffmpeg is **not bundled** in the portable build. It is only needed for downloading episodes.
Download size is approximately 60 MB; instructions are shown in the app if ffmpeg is not found.

---

## Roadmap

See [TODO.md](TODO.md).

---

## License

MIT
