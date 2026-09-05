# language: Python, file: main.py, target: FastAPI / Render
import httpx
import asyncio
import urllib.parse
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/info")
async def get_info(url: str):
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
                    dl_url = prog_data["download_url"]
                    
                    # NEW LOGIC: Instead of sending the blocked URL, we route it through our Proxy Stream
                    encoded_url = urllib.parse.quote(dl_url, safe="")
                    return {"url": f"/api/proxy?url={encoded_url}"}
                    
                elif prog_data.get("text") and "Error" in prog_data.get("text"):
                    raise HTTPException(status_code=400, detail="Target encountered an error.")
                    
            raise HTTPException(status_code=408, detail="Timeout waiting for engine.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/proxy")
async def proxy_download(url: str):
    """
    Takes the blocked third-party URL, downloads it via Render's US network,
    and streams it directly to the user's browser as a local attachment.
    """
    target_url = urllib.parse.unquote(url)
    
    client = httpx.AsyncClient()
    req = client.build_request("GET", target_url)
    
    try:
        r = await client.send(req, stream=True)
        
        if r.status_code != 200:
            await client.aclose()
            raise HTTPException(status_code=r.status_code, detail="Remote file server unreachable.")
            
        # Copy headers so the browser knows it's an MP4 file
        headers = {}
        if "Content-Disposition" in r.headers:
            headers["Content-Disposition"] = r.headers["Content-Disposition"]
        else:
            headers["Content-Disposition"] = "attachment; filename=youtube_video.mp4"
            
        if "Content-Type" in r.headers:
            headers["Content-Type"] = r.headers["Content-Type"]
            
        if "Content-Length" in r.headers:
            headers["Content-Length"] = r.headers["Content-Length"]

        async def stream_generator():
            try:
                # Stream the file in 1MB chunks to save Render's RAM
                async for chunk in r.aiter_bytes(chunk_size=1024*1024): 
                    yield chunk
            finally:
                await client.aclose()

        return StreamingResponse(stream_generator(), headers=headers)
    except Exception:
        await client.aclose()
        raise HTTPException(status_code=500, detail="Stream failed.")
