# language: Python, file: main.py, target: FastAPI / Render
# *direct extraction and metadata parsing route*
import os
import uuid
import yt_dlp
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

app = FastAPI()

def cleanup(file_path: str):
    if os.path.exists(file_path):
        os.remove(file_path)

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("index.html", "r") as f:
        return f.read()

@app.get("/api/info")
async def get_info(url: str):
    ydl_opts = {
        'quiet': True, 
        'skip_download': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            
            for f in info.get('formats', []):
                if f.get('vcodec') != 'none' and f.get('height'):
                    h = f['height']
                    filesize = f.get('filesize') or f.get('filesize_approx')
                    size_str = f"~{filesize / (1024*1024):.1f} MB" if filesize else "Available"
                    formats.append({'height': h, 'size': size_str})
            
            # Deduplicate resolutions
            unique = {x['height']: x for x in formats}
            sorted_formats = sorted(unique.values(), key=lambda x: x['height'], reverse=True)
            
            return {
                "title": info.get('title', 'Unknown Title'),
                "thumbnail": info.get('thumbnail', ''),
                "formats": sorted_formats
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/download")
async def download_video(url: str, height: int, background_tasks: BackgroundTasks):
    file_id = str(uuid.uuid4())
    out_tmpl = f"/tmp/{file_id}.%(ext)s"
    
    ydl_opts = {
        'format': f'bestvideo[height<={height}]+bestaudio/best',
        'outtmpl': out_tmpl,
        'merge_output_format': 'mp4',
        'quiet': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base, _ = os.path.splitext(filename)
            final_file = f"{base}.mp4"
            
        background_tasks.add_task(cleanup, final_file)
        clean_title = "".join(c for c in info.get('title', 'video') if c.isalnum() or c in " -_").strip()
        
        return FileResponse(
            path=final_file, 
            media_type='video/mp4', 
            filename=f"{clean_title}_{height}p.mp4"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
