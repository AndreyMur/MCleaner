# OmniCleaner

> Cross-platform desktop application for managing system packages and cleaning up cache and orphaned dependencies.

OmniCleaner is a modern desktop app built with **Tauri 2**, **React** and **Rust**. It bundles a Python reference backend that implements adapters for the major package managers, detects the host OS at startup and lets you:

- view dashboard stats (cache size, installed package count, OS);
- list installed packages with search and filtering;
- remove packages with dry-run planning and dependency cleanup (`autoremove`);
- clean package manager caches;
- remove orphaned packages safely;
- request privileges seamlessly (UAC / polkit / osascript) only when needed;
- interrupt long-running operations;
- create recovery points (Timeshift / System Restore / Time Machine);
- run in light or dark theme with automatic system detection.

## Supported platforms and package managers

| Platform | Package manager |
| --- | --- |
| Windows | `winget` |
| macOS | `homebrew` |
| Linux (Debian/Ubuntu) | `apt` |
| Linux (Fedora) | `dnf` |
| Linux (Arch) | `pacman` |
| Linux (openSUSE) | `zypper` |

## Installation

Prebuilt installers are published to [GitHub Releases](https://github.com/AndreyMur/MCleaner/releases):

- **Windows** — `.exe` (NSIS installer)
- **macOS** — `.dmg`
- **Linux** — `.deb` and `.AppImage`

## Development

### Prerequisites

- [Node.js](https://nodejs.org) 20+ (npm)
- [Rust](https://rustup.rs) stable toolchain
- Platform dependencies for [Tauri v2](https://v2.tauri.app/start/prerequisites/):
  - **Windows**: WebView2 (preinstalled on Windows 11 / recent Windows 10)
  - **Linux**: `libwebkit2gtk-4.1-dev`, `libgtk-3-dev`, `libayatana-appindicator3-dev`, `librsvg2-dev`, `patchelf`, `xdg-utils`

### Run in development mode

The frontend lives in `src/frontend`, the Tauri/Rust shell in `src-tauri`.

```bash
# 1. install frontend dependencies
cd src/frontend
npm ci

# 2. from the repository root, start the desktop app (starts the vite dev server)
node src/frontend/node_modules/@tauri-apps/cli/tauri.js dev
```

### Frontend only (fast iteration with mocked data)

```bash
cd src/frontend
npm run dev      # serves http://localhost:1420
```

The UI falls back to realistic mock data when it is not running inside Tauri, so all pages can be developed in a plain browser.

## Tests

| Suite | Command | Where |
| --- | --- | --- |
| Backend (Python adapters) | `python -m pytest src/tests -q` | `src/tests` |
| Frontend type-check + build | `npm run build` | `src/frontend` |
| E2E (Playwright, browser) | `npm run test:e2e` | `src/frontend/e2e` |
| Rust unit tests | `cargo test` | `src-tauri` |

All suites are executed in CI on Windows, macOS and Linux.

## Building installers

```bash
# from the repository root; output goes to src-tauri/target/release/bundle/
node src/frontend/node_modules/@tauri-apps/cli/tauri.js build

# restrict bundle formats, e.g.
node src/frontend/node_modules/@tauri-apps/cli/tauri.js build --bundles deb,appimage   # Linux
node src/frontend/node_modules/@tauri-apps/cli/tauri.js build --bundles dmg             # macOS
node src/frontend/node_modules/@tauri-apps/cli/tauri.js build --bundles nsis            # Windows
```

Generated bundles land in:

```
src-tauri/target/release/bundle/nsis/       # Windows *.exe installer
src-tauri/target/release/bundle/dmg/        # macOS *.dmg
src-tauri/target/release/bundle/deb/        # Linux *.deb
src-tauri/target/release/bundle/appimage/   # Linux *.AppImage
```

### Smoke tests for installers

After building, smoke tests install/launch each produced installer on its native OS:

```bash
bash scripts/smoke/linux-smoke.sh   "src-tauri/target/release/bundle"   # Linux (.deb + .AppImage)
bash scripts/smoke/macos-smoke.sh   "src-tauri/target/release/bundle"   # macOS (.dmg)
powershell -File scripts/smoke/windows-smoke.ps1 "src-tauri\target\release\bundle"  # Windows (NSIS)
```

## Release process

Releases are automated with GitHub Actions (see `.github/workflows/`):

1. `ci.yml` — runs on every push/PR: Python backend tests, frontend build + Playwright e2e, Rust unit tests and build checks on **Windows, macOS and Linux**.
2. `release.yml` — triggered by pushing a version tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The release workflow:

- builds the app and creates native installers on all three operating systems;
- runs the installer smoke tests against the produced artifacts;
- publishes the installers as assets of a GitHub Release.

## Repository layout

```
.
├── .github/workflows/        # CI + release pipelines
├── scripts/smoke/            # installer smoke tests
├── docs/                     # PRD and implementation plan
├── src/
│   ├── backend/              # Python package-manager adapters (apt, dnf, pacman, zypper, winget, homebrew)
│   ├── frontend/             # React + Vite frontend
│   └── tests/                # pytest suite for the backend adapters
└── src-tauri/                # Tauri (Rust) shell and bundling config
```

## License

[MIT](LICENSE)
