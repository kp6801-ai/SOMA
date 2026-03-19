# SOMA — VS Code Extension

A VS Code extension for **SOMA (Generative DJ Intelligence)**, giving you full access to your track library, mix recommendations, transition scoring, and session management directly inside the editor.

## Features

### Sidebar Views

Open the **SOMA** panel from the Activity Bar to access three dedicated views:

- **Tracks** — Browse your full track library with BPM, key, and energy details. Right-click any track to find similar tracks or check compatible Camelot keys.
- **Moods & Subgenres** — Browse all available moods (detroit, berlin, melodic, minimal, dark, etc.) and click to see matching tracks.
- **Sessions** — View your created DJ sessions and their status.

### Commands

Open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`) and type `SOMA` to access:

| Command | Description |
|---------|-------------|
| **SOMA: Refresh Track Library** | Reload tracks from the API |
| **SOMA: Find Similar Tracks** | Find tracks similar to a selected track |
| **SOMA: Score Transition Between Two Tracks** | Pick two tracks and get a detailed transition score |
| **SOMA: Show Track Details** | View full metadata for a track |
| **SOMA: Show Compatible Camelot Keys** | List harmonic-compatible keys for a track |
| **SOMA: Start DJ Session** | Choose an arc type and duration to plan a full session |
| **SOMA: Browse Tracks by Mood** | Filter tracks by subgenre/mood profile |
| **SOMA: Plan BPM Journey** | Plan a multi-step BPM transition between two tempos |
| **SOMA: Find Bridge Tracks** | Find 1–3 bridge tracks to transition between subgenres |
| **SOMA: Dig Crate (Search Tracks)** | Search tracks by label, BPM range, or energy tag |
| **SOMA: Set API URL** | Configure the backend API endpoint |

### Session Panel

When you start a session, a webview panel opens showing the full planned tracklist with BPM targets, Camelot keys, and match scores.

## Requirements

- A running **SOMA backend** (FastAPI). By default the extension connects to `http://localhost:8000/api`.
- Start the backend with: `uvicorn main:app --reload`

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `soma.apiUrl` | `http://localhost:8000/api` | Base URL for the SOMA backend API |

You can change this via **Settings** or the **SOMA: Set API URL** command.

## Installation

### From Source

```bash
cd vscode-extension
npm install
npm run compile
```

Then press `F5` in VS Code to launch the Extension Development Host, or package with:

```bash
npx @vscode/vsce package
```

This produces a `.vsix` file you can install via `Extensions: Install from VSIX…` in the Command Palette.

## Development

```bash
npm run watch    # Compile on save
```

Press `F5` to launch the Extension Development Host for testing.
