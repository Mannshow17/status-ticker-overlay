# Status Ticker Overlay

A lightweight Windows desktop ticker that continuously displays real-time service health for key platforms used in K-12 environments.

Created using ChatGPT



![alt text](https://github.com/Mannshow17/status-ticker-overlay/blob/b4a62b5ea613a3b8745bfabf3c3549b80f210352/status%20ticker%20screenshot.png)


The overlay sits at the top of your screen (AppBar-style) and shows:

- 🟢 Operational  
- 🟡 Degraded  
- 🔴 Outage  

for:

- Securly (RSS)
- Cloudflare (Statuspage JSON)
- Google Workspace (Atom feed)
- Microsoft Cloud (HTML scrape)

Only active degraded/outage events are shown. If everything is healthy, the provider collapses to a simple **Operational** message.

Each provider entry is clickable and opens the relevant status or incident page.

---

## Features

- Always-on-top ticker bar (Windows AppBar)
- Reserves screen space so maximized apps sit below it
- Smooth scrolling status text
- Color-coded severity (green / yellow / red)
- Clickable incident links
- Automatic refresh
- US + Global incident filtering where applicable
- Modular architecture (GUI vs data sources vs Windows integration)
- No external monitoring agents required

Designed for NOC / MSP / K-12 operational awareness.

---


## Installation (Windows)

1) **Clone or download**
    - Clone with Git:
        ```powershell
        git clone https://github.com/Mannshow17/status-ticker-overlay.git
        ```
    - Or download the ZIP from GitHub, extract it, and open a terminal in the extracted folder.

2) **Install Python (3.10+)**
    - Verify:
      ```powershell
      py --version
      ```
    - If that fails, install Python from python.org and ensure **Add Python to PATH** is checked.

3) **Install dependencies (run from project root)**
     ```powershell
     pip install requests beautifulsoup4
     ```

5) **Run the app (run from project root)**
    - `py main.py`
    - ⚠ Do **not** run `GUI/tickerOverlay.py` directly (imports assume `main.py` is the entry point).

6) **Expected behavior**
    - A ticker bar appears at the top of your screen.
    - Screen space is reserved so maximized apps sit below it.
    - Providers show:
        - 🟢 Operational
        - 🟡 Degraded
        - 🔴 Outage
    - Provider text is clickable and opens the status/incident page.
    - Status refreshes automatically.

7) **Troubleshooting**
    - If imports fail, confirm you ran:
        - `py main.py`
      from the project root (not `py GUI\tickerOverlay.py`).
      - `__pycache__` folders are normal and are ignored by `.gitignore`.



