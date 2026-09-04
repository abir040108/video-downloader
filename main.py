# language: Python, file: main.py, target: FastAPI / Render
# *updated to cobalt v7 api root endpoint and spoofed origin headers*
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
    # Fetching basic metadata via official oembed
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
    # Cobalt V7 strict headers
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://cobalt.tools",
        "Referer": "https://cobalt.tools/"
    }
    
    payload = {
        "url": url,
        "videoQuality": quality
    }
    
    # Fallback instances if the primary is heavily rate-limited
    instances = [
        "https://api.cobalt.tools/",
        "https://co.wuk.sh/"
    ]
    
    async with httpx.AsyncClient() as client:
        for engine in instances:
            try:
                resp = await client.post(engine, json=payload, headers=headers, timeout=20.0)
                
                if resp.status_code == 200:
                    data = resp.json()
                    # V7 returns status 'redirect' or 'tunnel' containing the url
                    if data.get("status") in ["redirect", "tunnel"] and "url" in data:
                        return {"url": data["url"]}
                    elif data.get("status") == "error":
                        continue # try the next instance
            except Exception:
                continue # silently try the next instance if connection drops
                
    raise HTTPException(status_code=500, detail="All extraction engines are currently blocked or overloaded.")
