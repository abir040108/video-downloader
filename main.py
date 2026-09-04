# language: Python, file: main.py, target: FastAPI / Render
# *hijacks commercial converter internal ajax api to offload downloading and muxing*
import httpx
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("index.html", "r") as f:
        return f.read()

@app.get("/api/info")
async def get_info(url: str):
    # Fast metadata via official oembed
    oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(oembed_url, timeout=10.0)
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
    # Spoofing the origin to bypass the target's CORS and basic bot protection
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://en.loader.to",
        "Referer": "https://en.loader.to/"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # Step 1: Inject URL into their backend conversion queue
            init_url = f"https://loader.to/ajax/download.php?format={quality}&url={url}"
            init_resp = await client.get(init_url, headers=headers, timeout=15.0)
            init_data = init_resp.json()
            
            task_id = init_data.get("id")
            if not task_id:
                raise HTTPException(status_code=400, detail="Hijack failed. Target API rejected payload.")
            
            # Step 2: Poll their internal status endpoint until the file is muxed and ready
            progress_url = f"https://loader.to/ajax/progress.php?id={task_id}"
            
            for _ in range(40): # Poll for up to 80 seconds while their servers work
                await asyncio.sleep(2)
                prog_resp = await client.get(progress_url, headers=headers, timeout=10.0)
                prog_data = prog_resp.json()
                
                if prog_data.get("success") == 1 and prog_data.get("download_url"):
                    return {"url": prog_data["download_url"]}
                elif prog_data.get("text") and "Error" in prog_data.get("text"):
                    raise HTTPException(status_code=400, detail="Target API encountered an error processing the video.")
                    
            raise HTTPException(status_code=408, detail="Timeout waiting for remote engine to finish.")
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
