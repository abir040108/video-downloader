# language: Python, file: main.py, target: FastAPI / Render
# *added invidious api hijacking to pre-calculate file sizes via bitrate*
import httpx
import asyncio
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
                        # Find the video stream to calculate size
                        stream = next((s for s in streams if s.get("resolution") == f"{h}p" or s.get("qualityLabel") == f"{h}p"), None)
                        size_str = "Size varies"
                        
                        if stream and stream.get("bitrate") and data.get("lengthSeconds"):
                            # Bitrate (bits/sec) * Duration (sec) / 8 = Bytes
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
                
        # Fallback if all Invidious instances are dead
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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://en.loader.to",
        "Referer": "https://en.loader.to/"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            init_url = f"https://loader.to/ajax/download.php?format={quality}&url={url}"
            init_resp = await client.get(init_url, headers=headers, timeout=15.0)
            init_data = init_resp.json()
            
            task_id = init_data.get("id")
            if not task_id:
                raise HTTPException(status_code=400, detail="Target API rejected payload.")
            
            progress_url = f"https://loader.to/ajax/progress.php?id={task_id}"
            
            for _ in range(40):
                await asyncio.sleep(2)
                prog_resp = await client.get(progress_url, headers=headers, timeout=10.0)
                prog_data = prog_resp.json()
                
                if prog_data.get("success") == 1 and prog_data.get("download_url"):
                    return {"url": prog_data["download_url"]}
                elif prog_data.get("text") and "Error" in prog_data.get("text"):
                    raise HTTPException(status_code=400, detail="Target encountered an error.")
                    
            raise HTTPException(status_code=408, detail="Timeout waiting for engine.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
