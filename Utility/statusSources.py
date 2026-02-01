# Utility/status_sources.py
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import requests

from GUI import uiConfig

TIMEOUT = 12

# ----------------------------
# SOURCES
# ----------------------------
CLOUDFLARE_SUMMARY_URL = "https://www.cloudflarestatus.com/api/v2/summary.json"
CLOUDFLARE_STATUS_PAGE = "https://www.cloudflarestatus.com/"


GOOGLE_ATOM_URL = "https://www.google.com/appsstatus/dashboard/en/feed.atom"
GOOGLE_STATUS_PAGE = "https://www.google.com/appsstatus/dashboard/"

SECURLY_RSS_URL = "https://status.io/pages/5721276eb12b2e5843002acb/rss"
SECURLY_STATUS_PAGE = "https://securly.status.io/"


MICROSOFT_STATUS_PAGE = "https://status.cloud.microsoft/"



# ----------------------------
# WHAT YOU CARE ABOUT
# ----------------------------
GOOGLE_WATCHLIST = {
    "Gmail",
    "Google Drive",
}

US_HINTS = [
    "united states", "u.s.", " us ", "usa", "north america", "americas",
    "us-east", "us west", "us-west", "united states of america",
]
GLOBAL_HINTS = [
    "global", "worldwide", "all regions", "all locations", "all data centers",
    "multiple regions",
]
NON_US_HINTS = [
    "europe", "emea", "apac", "asia", "australia", "new zealand",
    "japan", "korea", "india", "singapore", "hong kong", "taiwan",
    "china", "middle east", "africa", "south america", "latin america",
    "canada", "mexico", "uk", "united kingdom", "germany", "france",
    "spain", "italy", "netherlands", "sweden", "norway", "finland",
    "poland", "brazil", "argentina", "chile",
]


# ----------------------------
# HELPERS
# ----------------------------
def norm(s: str) -> str:
    return (s or "").strip().lower()

def has_any(text: str, needles: list[str]) -> bool:
    t = norm(text)
    return any(n in t for n in needles)

def relevant_to_us_or_global(title: str, body: str) -> bool:
    blob = f"{title}\n{body}".strip()
    t = norm(blob)

    us = has_any(t, US_HINTS)
    glob = has_any(t, GLOBAL_HINTS)
    non_us = has_any(t, NON_US_HINTS)

    if us or glob:
        return True
    if non_us:
        return False
    return True  # unknown => include (safe)

SEV_OK = 0
SEV_DEGRADED = 1
SEV_OUTAGE = 2

def sev_max(a: int, b: int) -> int:
    return a if a >= b else b

def infer_sev_from_words(text: str) -> int:
    t = norm(text)
    outage_words = ["outage", "major outage", "critical", "down", "service outage", "service disruption"]
    degraded_words = ["degraded", "partial", "minor", "performance", "incident", "maintenance", "under maintenance", "disruption"]

    if any(w in t for w in outage_words):
        return SEV_OUTAGE
    if any(w in t for w in degraded_words):
        return SEV_DEGRADED
    if "operational" in t or "available" in t or "all systems operational" in t:
        return SEV_OK
    return SEV_DEGRADED

def color_for_sev(sev: int) -> str:
    if sev == SEV_OUTAGE:
        return uiConfig.COLOR_OUTAGE
    if sev == SEV_DEGRADED:
        return uiConfig.COLOR_DEGRADED
    return uiConfig.COLOR_OK

# ----------------------------
# FETCHERS
# ----------------------------
def fetch_cloudflare():
    r = requests.get(CLOUDFLARE_SUMMARY_URL, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()

    indicator = (data.get("status", {}).get("indicator") or "unknown").lower()
    if indicator == "none":
        return {"text": "Cloudflare: Operational", "sev": SEV_OK, "url": None, "clickable": False}

    incidents = data.get("incidents", []) or []
    relevant_titles = []
    worst = SEV_OK
    best_url = CLOUDFLARE_STATUS_PAGE

    for inc in incidents:
        title = inc.get("name", "") or ""
        updates = inc.get("incident_updates", []) or []
        body = updates[0].get("body", "") if updates else ""

        if not relevant_to_us_or_global(title, body):
            continue

        impact = (inc.get("impact") or "").lower()
        sev = SEV_DEGRADED if impact == "minor" else SEV_OUTAGE if impact in ("major", "critical") else infer_sev_from_words(title + " " + body)
        worst = sev_max(worst, sev)

        if title.strip():
            relevant_titles.append(title.strip())

        if inc.get("shortlink"):
            best_url = inc["shortlink"]

    if not relevant_titles:
        return {"text": "Cloudflare: Operational", 
                "sev": SEV_OK, 
                "url": None, 
                "clickable": True
            }

    header = "Outage" if worst == SEV_OUTAGE else "Degraded"
    details = "; ".join(relevant_titles[:2])
    return {"text": f"Cloudflare: {header} — {details}", 
            "sev": worst, 
            "url": best_url, 
            "clickable": True
        }


def fetch_google_workspace():
    r = requests.get(GOOGLE_ATOM_URL, timeout=TIMEOUT)
    r.raise_for_status()

    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(r.text)

    entries = root.findall("a:entry", ns)

    impacted = []
    worst = SEV_OK
    best_url = GOOGLE_STATUS_PAGE

    for e in entries:
        title = (e.findtext("a:title", default="", namespaces=ns) or "").strip()
        title_l = title.lower()

        # Skip resolved incidents
        if title_l.startswith("resolved:"):
            continue

        summary = (e.findtext("a:summary", default="", namespaces=ns) or "").strip()

        # Infer severity from text (title + summary)
        sev = infer_sev_from_words(title + " " + summary)

        # Only keep degraded/outage
        if sev == SEV_OK:
            continue

        # No nested loop: directly find the alternate link
        link_el = e.find("a:link[@rel='alternate']", ns)
        link_url = (link_el.get("href") or "").strip() if link_el is not None else ""

        # Prefer first incident URL we find
        if link_url and best_url == GOOGLE_STATUS_PAGE:
            best_url = link_url

        worst = sev_max(worst, sev)
        impacted.append(" ".join(title.split()))  # normalize whitespace/newlines

    # If nothing active + degraded/outage, report overall operational
    if not impacted:
        return {
            "text": "Google Workspace: Operational",
            "sev": SEV_OK,
            "url": GOOGLE_STATUS_PAGE,
            "clickable": True
        }

    header = "Outage" if worst == SEV_OUTAGE else "Degraded"
    details = "; ".join(impacted[:2])

    return {
        "text": f"Google Workspace: {header} — {details}",
        "sev": worst,
        "url": best_url or GOOGLE_STATUS_PAGE,
        "clickable": True
    }





def fetch_securly():
    r = requests.get(SECURLY_RSS_URL, timeout=TIMEOUT)
    r.raise_for_status()

    root = ET.fromstring(r.text)

    # RSS namespace handling (status.io uses plain RSS2)
    items = root.findall(".//item")

    active = []
    worst = SEV_OK
    best_url = SECURLY_STATUS_PAGE

    for item in items:
        title = (item.findtext("title") or "").strip()
        desc = (item.findtext("description") or "").lower()
        link = (item.findtext("link") or "").strip()

        # Skip resolved incidents
        if "resolved" in desc:
            continue

        sev = infer_sev_from_words(title + " " + desc)
        worst = sev_max(worst, sev)

        if title:
            active.append(title)

        if link:
            best_url = link

    # No active incidents
    if not active:
        return {
            "text": "Securly: Operational",
            "sev": SEV_OK,
            "url": best_url,
            "clickable": True
        }

    header = "Outage" if worst == SEV_OUTAGE else "Degraded"
    details = "; ".join(active[:2])

    return {
        "text": f"Securly: {header} — {details}",
        "sev": worst,
        "url": best_url,
        "clickable": True
    }


def fetch_microsoft():
    r = requests.get(MICROSOFT_STATUS_PAGE, timeout=TIMEOUT)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    lines = [ln.strip() for ln in soup.get_text("\n").splitlines() if ln.strip()]

    incidents = []
    worst = SEV_OK
    best_url = MICROSOFT_STATUS_PAGE
    saw_all_operational = False

    for ln in lines:
        l = ln.lower()

        # 1) Detect the "everything is fine" banner
        if "all systems operational" in l:
            saw_all_operational = True
            # don't return yet; keep scanning in case the page contains both phrases

        # 2) Collect possible incident lines
        if any(word in l for word in ("outage", "degraded", "incident", "disruption")):
            if not relevant_to_us_or_global(ln, ln):
                continue

            sev = infer_sev_from_words(ln)
            worst = sev_max(worst, sev)
            incidents.append(ln)

    # If we found any relevant incidents, show them
    if incidents:
        header = "Outage" if worst == SEV_OUTAGE else "Degraded"
        details = "; ".join(incidents[:2])
        return {
            "text": f"Microsoft Cloud: {header} — {details}",
            "sev": worst,
            "url": best_url,
            "clickable": True
        }

    # Otherwise, treat as operational
    # Prefer the explicit banner if present, but either way operational is fine
    if saw_all_operational or not incidents:
        return {
            "text": "Microsoft Cloud: Operational",
            "sev": SEV_OK,
            "url": best_url,
            "clickable": True
        }




def build_segments():
    return [fetch_securly(), fetch_cloudflare(), fetch_google_workspace(), fetch_microsoft()]
