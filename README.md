# Clash of Clans Educational Automation Bot

An educational project demonstrating **computer vision**, **GUI automation**, **state machines**, and **game AI** by automating Clash of Clans on Google Play Games Developer Emulator.

> [!WARNING]
> This is an **educational project** for learning purposes only. Using bots on live accounts violates Supercell's Terms of Service and will result in a permanent ban. Use a throwaway/test account only.

## Prerequisites

1. Python 3.11+
2. **Google Play Games Developer Emulator**: The consumer version doesn't expose ADB.
   - Requires Hyper-V enabled in Windows.
   - Download the Developer Emulator from the Google Android Developer site.
3. Clash of Clans installed in the emulator.

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

1. Start the Google Play Games Developer Emulator and launch Clash of Clans.
2. Ensure ADB can connect to it (defaults to `localhost:6520`):
   ```bash
   python main.py test-adb
   ```
3. Use the tools to capture UI templates from the game:
   ```bash
   python main.py capture
   ```
4. Define screen regions in `config/game_config.yaml` using:
   ```bash
   python main.py regions
   ```
5. Run the bot in dry-run mode to verify vision/state detection:
   ```bash
   python main.py run --dry-run
   ```
6. Run the bot:
   ```bash
   python main.py run
   ```

## Architecture

The bot uses a classic game loop:
1. **Capture**: Grabs the screen via ADB `screencap`
2. **Analyze**: Uses OpenCV template matching and HSV color detection to read the screen
3. **Decide**: A finite state machine (FSM) dispatches the current state to a specific Strategy
4. **Act**: Sends tap/swipe commands back via ADB

## Adding Custom Strategies

To add new behaviors, create a new class inheriting from `Strategy` in `modules/decision/strategies/`, and register it in the `DecisionEngine`.

## Disclaimer

This software is provided for educational purposes to demonstrate computer vision and test automation techniques. The author is not responsible for banned accounts or misuse of this software.
