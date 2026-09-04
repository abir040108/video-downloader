# language: Python, file: main.py, target: FastAPI / Render
# *offloads extraction to a public evasion engine to bypass datacenter ip bans*
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import httpx

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("index.html", "r") as f:
        return f.read()

@app.get("/api/info")
async def get_info(url: str):
    # Uses YouTube's official open oEmbed API to fetch metadata without triggering 403s
    oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(oembed_url, timeout=10.0)
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Invalid YouTube link.")
            data = resp.json()
            return {
                "title": data.get("title", "Unknown Video"), 
                "thumbnail": data.get("thumbnail_url", ""), 
                "formats": [1080, 720, 480, 360]
            }
        except:
            raise HTTPException(status_code=400, detail="Metadata extraction failed.")

@app.get("/api/download")
async def get_download_link(url: str, quality: str = "1080"):
    # Payload for the upstream proxy engine
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    payload = {
        "url": url,
        "videoQuality": quality,
        "filenamePattern": "classic"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # Hitting an open evasion instance
            resp = await client.post("https://api.cobalt.tools/api/json", json=payload, headers=headers, timeout=20.0)
            data = resp.json()
            
            if "url" in data:
                return {"url": data["url"]}
            else:
                raise HTTPException(status_code=400, detail="Upstream engine failed to extract direct link.")
        except Exception as e:
            raise HTTPException(status_code=500, detail="Upstream engine offline or blocked.")
