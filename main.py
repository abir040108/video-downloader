# language: Python, file: main.py, target: FastAPI / Render
# *dynamically hunts through live community nodes to bypass overloading*
import httpx
import re
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

app = FastAPI()

def get_yt_id(url: str):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("index.html", "r") as f:
        return f.read()

@app.get("/api/info")
async def get_info(url: str):
    vid_id = get_yt_id(url)
    if not vid_id:
        raise HTTPException(status_code=400, detail="Invalid link.")
        
    # Hijack Invidious APIs to scrape stream bitrates for size calculation
    instances = [
        "https://vid.puffyan.us",
        "https://invidious.jing.rocks",
        "https://invidious.nerdvpn.de"
    ]
    
    async with httpx.AsyncClient() as client:
        for instance in instances:
            try:
                resp = await client.get(f"{instance}/api/v1/videos/{vid_id}", timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    formats = []
                    target_heights = [1080, 720, 480, 360]
                    streams = data.get("adaptiveFormats", []) + data.get("formatStreams", [])
                    
                    for h in target_heights:
                        stream = next((s for s in streams if s.get("resolution") == f"{h}p" or s.get("qualityLabel") == f"{h}p"), None)
                        size_str = "Est. Dynamically"
                        if stream and stream.get("bitrate") and data.get("lengthSeconds"):
                            bytes_size = (int(stream["bitrate"]) * int(data["lengthSeconds"])) / 8
                            mb_size = bytes_size / (1024 * 1024)
                            size_str = f"~{mb_size:.1f} MB"
                        formats.append({"height": h, "size": size_str})
                        
                    return {
                        "title": data.get("title", "Unknown Video"),
                        "thumbnail": f"https://img.youtube.com/vi/{vid_id}/maxresdefault.jpg",
                        "formats": formats
                    }
            except Exception:
                continue
                
        # Fallback if Invidious is blocked
        try:
            oembed = await client.get(f"https://www.youtube.com/oembed?url={url}&format=json")
            odata = oembed.json()
            return {
                "title": odata.get("title", "Unknown"),
                "thumbnail": odata.get("thumbnail_url", ""),
                "formats": [{"height": h, "size": "Est. Dynamically"} for h in [1080, 720, 480, 360]]
            }
        except:
            raise HTTPException(status_code=400, detail="Metadata extraction failed.")

@app.get("/api/download")
async def get_download_link(url: str, quality: str = "1080"):
    payload = {
        "url": url,
        "videoQuality": quality,
        "filenamePattern": "classic"
    }
    
    # Base fallback nodes if the registry goes down
    nodes = [
        "https://co.wuk.sh",
        "https://cobalt.q0.o.u00z.com",
        "https://cobalt.canine.ly",
        "https://cobalt.owo.vc"
    ]
    
    async with httpx.AsyncClient() as client:
        # 1. Fetch live community nodes from the global registry
        try:
            registry = await client.get("https://instances.cobalt.wiki/instances.json", timeout=5.0)
            if registry.status_code == 200:
                data = registry.json()
                # Filter for instances that are flagged as online
                live_nodes = [f"https://{n['domain']}" for n in data if n.get("up", True) and n.get("api_online", True)]
                if live_nodes:
                    nodes = live_nodes + nodes
        except Exception:
            pass 
            
        # Deduplicate while preserving order
        seen = set()
        unique_nodes = [x for x in nodes if not (x in seen or seen.add(x))]
        
        # 2. Fire the payload at community nodes until one accepts it
        for engine in unique_nodes[:15]: # Cap at 15 attempts to prevent endless hanging
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            try:
                # Cobalt V7 accepts POST directly to the root endpoint
                resp = await client.post(engine, json=payload, headers=headers, timeout=12.0)
                if resp.status_code == 200:
                    data = resp.json()
                    # A successful extraction returns a direct URL or tunnel stream
                    if data.get("status") in ["redirect", "tunnel", "stream"] and "url" in data:
                        return {"url": data["url"]}
            except Exception:
                continue # Node is dead or blocked by Cloudflare. Silently move to the next.
                
    raise HTTPException(status_code=500, detail="All community extraction nodes are currently overloaded.")
