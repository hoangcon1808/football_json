import requests
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ================= HTTP =================
session = requests.Session()
session.headers.update(HEADERS)

def fetch_json(url):
    try:
        r = session.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return {}

# ================= STREAM CHECK =================
def is_working_m3u8(url):
    if ".m3u8" not in url:
        return False
    try:
        r = session.head(url, timeout=3)
        return r.status_code == 200
    except:
        return False

def is_valid_tv(url):
    if ".m3u8" not in url:
        return False
    if any(x in url for x in ["udp://", "rtp://"]):
        return False
    return True

def check_stream(url):
    if is_valid_tv(url):
        return url if is_working_m3u8(url) else None
    return None

# ================= PICK STREAM =================
def pick_stream(streams):
    m3u8_hd = None
    m3u8 = None
    for s in streams:
        name = s.get("name", "").upper()
        url = s.get("sourceUrl")
        if not url:
            continue
        if ".m3u8" in url:
            if "FHD" in name or "HD" in name:
                m3u8_hd = url
            else:
                m3u8 = url
    return m3u8_hd or m3u8

# ================= API STANDARD =================
def process_standard(url, group):
    out = []
    data = fetch_json(url)
    for item in data.get("data", []):
        dt = datetime.now()
        if item.get("startTime"):
            try:
                dt = datetime.strptime(item["startTime"][:19], "%Y-%m-%dT%H:%M:%S") + timedelta(hours=7)
            except:
                pass
        for c in item.get("fixtureCommentators", []):
            comm = c.get("commentator", {})
            blv_name = comm.get("name", "Chính")
            stream = pick_stream(comm.get("streams", []))
            if not stream:
                continue
            out.append({
                "time": dt,
                "group": group,
                "title": f'{dt.strftime("%H:%M")} | {item.get("title")}',
                "logo": item.get("homeTeam", {}).get("logoUrl", ""),
                "url": stream,
                "blv": blv_name
            })
            break
    return out

# ================= HỘI QUÁN 2 / GIỜ VÀNG TV =================
def process_hoiquan2(url, group_name="HỘI QUÁN 2"):
    out = []
    data = fetch_json(url)
    for group in data.get("groups", []):
        for ch in group.get("channels", []):
            dt = datetime.now()
            streams = ch.get("sources", [])[0].get("contents", [])[0].get("streams", [])
            stream_url = None
            if streams:
                links = streams[0].get("stream_links", [])
                if links:
                    stream_url = links[0].get("url")
            out.append({
                "time": dt,
                "group": group_name,
                "title": ch.get("name"),
                "logo": ch.get("image", {}).get("url", ""),
                "url": stream_url,
                "blv": "Mặc định"
            })
    return out

# ================= VONG CAM =================
def process_vongcam():
    out = []
    data = fetch_json("https://sv.bugiotv.xyz/internal/api/matches")
    for item in data.get("data", []):
        url = item.get("commentator", {}).get("streamSourceFhd")
        blv_name = item.get("commentator", {}).get("name", "Chính")
        if not url or ".m3u8" not in url:
            continue
        out.append({
            "time": datetime.now(),
            "group": "VÒNG CẤM TV",
            "title": item.get("title"),
            "logo": item.get("homeClub", {}).get("logoUrl", ""),
            "url": url,
            "blv": blv_name
        })
    return out

# ================= CO LA =================
def process_cala_tv():
    out = []
    data = fetch_json("https://api.cltvlv.com/api/matches")
    for key, item in data.get("data", {}).items():
        dt = datetime.fromtimestamp(item.get("matchTime", datetime.now().timestamp()))
        home = item.get("home_team", {})
        away = item.get("away_team", {})
        streams = item.get("anchorAppointmentVoList", [])
        stream_url = None
        blv_name = "Chính"
        for s in streams:
            if s.get("anchorName"):
                blv_name = s.get("anchorName")
            for k in ["playStreamAddress2", "playStreamAddress1", "playStreamAddress3"]:
                if s.get(k) and ".m3u8" in s[k]:
                    stream_url = s[k]
                    break
            if stream_url:
                break
        out.append({
            "time": dt,
            "group": "CO LA TV",
            "title": f'{dt.strftime("%H:%M")} | {home.get("name")} vs {away.get("name")}',
            "logo": home.get("logo", ""),
            "url": stream_url,
            "blv": blv_name
        })
    return out

# ================= TAM QUOC =================
def process_tamquoc_tv():
    out = []
    data = fetch_json("https://sv.tamquoctv.xyz/internal/api/matches")
    items = data.get("data", [])
    if isinstance(items, dict):
        items = items.values()
    for item in items:
        dt = datetime.now()
        if item.get("startTime"):
            try:
                dt = datetime.strptime(item["startTime"][:19], "%Y-%m-%dT%H:%M:%S")
            except:
                pass
        home = item.get("homeClub", {})
        away = item.get("awayClub", {})
        commentator = item.get("commentator", {})
        blv_name = commentator.get("name", "Chính")
        stream_url = (
            commentator.get("streamSourceFhd") or
            commentator.get("streamSourceHd") or
            commentator.get("streamSourceSd")
