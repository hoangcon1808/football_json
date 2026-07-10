import requests
import re
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
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
            sources = ch.get("sources", [])
            if not sources:
                continue
            contents = sources[0].get("contents", [])
            if not contents:
                continue
            streams = contents[0].get("streams", [])
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
        
        stream_url = commentator.get("streamSourceFhd") or commentator.get("streamSourceHd") or commentator.get("streamSourceSd")
        if not stream_url or ".m3u8" not in stream_url:
            continue
            
        out.append({
            "time": dt,
            "group": "TAM QUOC TV",
            "title": f'{dt.strftime("%H:%M")} | {home.get("name")} vs {away.get("name")}',
            "logo": home.get("logoUrl", ""),
            "url": stream_url,
            "blv": blv_name
        })
    return out

# ================= LUONG SON TV / QUE CHOA TV =================
def process_quechoa_tv(url, group_name="QUECHOA TV"):
    out = []
    data = fetch_json(url)
    for group in data.get("groups", []):
        for ch in group.get("channels", []):
            dt = datetime.now()
            logo = ch.get("image", {}).get("url", "")
            title = ch.get("name", "")
            for src in ch.get("sources", []):
                blv_name = src.get("name", "Chính")
                for content in src.get("contents", []):
                    for stream in content.get("streams", []):
                        links = stream.get("stream_links", [])
                        if links:
                            stream_url = links[0].get("url")
                            out.append({
                                "time": dt,
                                "group": group_name,
                                "title": title,
                                "logo": logo,
                                "url": stream_url,
                                "blv": blv_name
                            })
    return out

# ================= LOAD FPT SPORT =================
def load_fpt_sport(url, group_name="FPT SPORT"):
    out = []
    try:
        r = session.get(url, timeout=15)
        lines = r.text.splitlines()
        title = ""
        for line in lines:
            if line.startswith("#EXTINF"):
                title = line.split(",")[-1].strip()
            elif line.startswith("http"):
                out.append({
                    "time": datetime.now(),
                    "group": group_name,
                    "title": title if title else group_name,
                    "logo": "",
                    "url": line.strip(),
                    "blv": "FPT"
                })
    except Exception as e:
        print(f"Error loading FPT Sport: {e}")
    return out

# ================= WRITE FILE M3U =================
def write_files(data):
    seen = set()
    tv = "#EXTM3U\n"
    full = "#EXTM3U\n"
    live_items = []
    items = []
    
    for item in data:
        url = item["url"]
        if not url or url in seen:
            continue
        seen.add(url)
        extinf = f'#EXTINF:-1 group-title="{item["group"]}" tvg-logo="{item["logo"]}",{item["title"]}\n'
        items.append((extinf, url, item))

    for extinf, url, item in items:
        monplayer_url = f"{url}|User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        full += extinf + f"{monplayer_url}\n\n"

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {}
        for extinf, url, item in items:
            if item["group"] in ["HỘI QUÁN 2", "LƯƠNG SƠN TV", "QUECHOA TV", "GIỜ VÀNG", "QUÊ CHOA"]:
                monplayer_url = f"{url}|User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                tv += extinf + f"{monplayer_url}\n\n"
                live_items.append(item)
            else:
                futures[executor.submit(check_stream, url)] = (extinf, url, item)
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                extinf, url, item = futures[future]
                monplayer_url = f"{url}|User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                tv += extinf + f"{monplayer_url}\n\n"
                live_items.append(item)

    with open("tv.m3u", "w", encoding="utf-8") as f:
        f.write(tv)
    with open("full.m3u", "w", encoding="utf-8") as f:
        f.write(full)
        
    print(f"TV Channels: {tv.count('#EXTINF')}")
    print(f"FULL Channels: {full.count('#EXTINF')}")
    return live_items

# ================= CONVERT TO JSON (MONPLAYER STANDARD) =================
def write_json(data):
    output = {
        "id": "tonghop",
        "url": "https://hoangcon.io.vn",
        "name": "HoangConTV",
        "color": "#1cb57a",
        "grid_number": 3,
        "image": {
            "type": "cover",
            "url": "https://kaytee1012.github.io/hoiquan_logo.png"
        },
        "notice": {
            "closeable": True,
            "icon": "https://kaytee1012.github.io/pngegg.png",
            "id": "notice",
            "link": "https://t.me/", 
            "text": "Nhóm Telegram"
        },
        "groups": []
    }
    
    groups_map = {}
    for idx, item in enumerate(data):
        group_id = item["group"]
        if group_id not in groups_map:
            groups_map[group_id] = {
                "id": group_id.lower().replace(" ", "-"),
                "name": f"🔴 {group_id}",
                "display": "vertical",
                "grid_number": 2,
                "enable_detail": False,
                "channels": []
            }
            
        label_text = "● Live" if item.get("url") else "⏳ Chưa live"
        label_color = "#ff0000" if item.get("url") else "#d54f1a"
        blv_real_name = item.get("blv", "F")
        
        # Thêm idx để tránh trùng lặp ID khi nhiều trận đấu diễn ra cùng giờ
        channel_id = f'{group_id.lower().replace(" ", "-")}-{item["time"].strftime("%H%M%S")}-{idx}'
        
        stream_url = ""
        if item.get("url"):
            # Gắn trực tiếp định dạng chuỗi User-Agent vào URL thay vì bọc trong block Object headers
            stream_url = f"{item['url']}|User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        
        channel = {
            "id": channel_id,
            "name": f'⚽ {item["title"]}',
            "type": "single",
            "display": "thumbnail-only",
            "enable_detail": False,
            "image": {
                "padding": 1,
                "background_color": "#ececec",
                "display": "contain",
                "url": item["logo"],
                "width": 1600,
                "height": 1200
            },
            "labels": [{
                "text": label_text,
                "position": "top-left",
                "color": "#00ffffff",
                "text_color": label_color
            }],
            "sources": [{
                "id": channel_id,
                "name": group_id,
                "contents": [{
                    "id": channel_id,
                    "name": item["title"],
                    "streams": [{
                        "id": channel_id,
                        "name": blv_real_name,
                        "stream_links": [{
                            "id": "lnk-1",
                            "name": "Link 1",
                            "type": "hls",
                            "default": True,
                            "url": stream_url
                        }] if stream_url else []
                    }]
                }]
            }]
        }
        groups_map[group_id]["channels"].append(channel)
        
    output["groups"] = list(groups_map.values())
    with open("channel.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("JSON file channel.json chuẩn MonPlayer đã được tạo ✔")

# ================= TRANG ĐÍCH 1-CLICK MONPLAYER =================
def write_html():
    html = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>HoangConTV - Nạp Nguồn MonPlayer</title>
    <style>
        body { 
            background-color: #0b0c10; display: flex; justify-content: center; 
            align-items: center; height: 100vh; margin: 0; font-family: 'Courier New', monospace; 
        }
        .cyber-btn {
            background: transparent; color: #0ff; border: 2px solid #0ff;
            padding: 15px 30px; font-size: 20px; font-weight: bold;
            text-transform: uppercase; text-decoration: none;
            box-shadow: 0 0 10px #0ff, inset 0 0 10px #0ff;
            text-shadow: 0 0 5px #0ff; transition: 0.3s; position: relative;
            cursor: pointer; border-radius: 4px;
        }
        .cyber-btn:hover {
            background: #0ff; color: #000; box-shadow: 0 0 25px #0ff, inset 0 0 20px #0ff;
        }
    </style>
</head>
<body>
    <a href="monplayer://add-provider?url=https://hoangcon.io.vn/channels.json" class="cyber-btn">
       [+] THÊM VÀO MONPLAYER
    </a>
</body>
</html>"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML Index (Neon UI) đã được tạo ✔")

# ================= MAIN =================
if __name__ == "__main__":
    data = []
    print("Đang tải dữ liệu từ các nguồn...")
    data += process_standard("https://sv.hoiquantv.xyz/api/v1/external/fixtures/unfinished", "HỘI QUÁN 1")
    data += process_hoiquan2("https://pub-26bab83910ab4b5781549d12d2f0ef6f.r2.dev/hoiquan1.json", "HỘI QUÁN 2")
    data += process_standard("https://sv.thiendinhtv.xyz/api/v1/external/fixtures/unfinished", "THIÊN ĐÌNH")
    data += process_standard("https://sv.xaycontv.xyz/api/v1/external/fixtures/unfinished", "XAY CON")
    data += process_vongcam()
    data += process_cala_tv()
    data += process_tamquoc_tv()
    data += process_hoiquan2("https://raw.githubusercontent.com/jasminliu98/giovang-stream/refs/heads/main/output.json", "GIỜ VÀNG")
    data += process_quechoa_tv("https://raw.githubusercontent.com/huybuonvp/xem_football/refs/heads/main/All_CHANNEL.json", "QUÊ CHOA")
    data += load_fpt_sport("https://raw.githubusercontent.com/Bacbenny/testtieulam/refs/heads/main/output/iptv.m3u", "TIẾU LÂM TV")
    
    live_data = write_files(data)
    write_json(data)
    write_html()
    print("DONE PRO MAX++ ✔")
