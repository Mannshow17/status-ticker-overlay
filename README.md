# Status Ticker Overlay

A lightweight Windows desktop ticker that continuously displays real-time service health for key platforms used in K-12 environments.

Created using ChatGPT

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


## Requirements

- Windows
- Python 3.10+ (tested on 3.14)
- Internet access

Python packages:

requests
beautifulsoup4

Always run from the project loop:

main.py


