# language: Python, file: main.py, target: FastAPI / Docker
# *processes video+audio muxing before serving. handles transient file cleanup.*
import os
import uuid
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
import yt_dlp

app = FastAPI()

def cleanup(file_path: str):
    if os.path.exists(file_path):
        os.remove(file_path)

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("index.html", "r") as f:
        return f.read()

@app.get("/api/info")
def get_info(url: str):
    ydl_opts = {'quiet': True, 'skip_download': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = []
        
        # Parse available video resolutions
        for f in info.get('formats', []):
            if f.get('vcodec') != 'none' and f.get('resolution') and f.get('height'):
                formats.append({
                    'format_id': f['format_id'],
                    'resolution': f.get('resolution'),
                    'height': f['height'],
                    'ext': f.get('ext')
                })
        
        # Deduplicate by height, prioritizing the best streams
        unique_formats = {}
        for f in formats:
            h = f['height']
            if h not in unique_formats:
                unique_formats[h] = f
        
        sorted_formats = sorted(unique_formats.values(), key=lambda x: x['height'], reverse=True)
        return {
            "title": info.get('title', 'Unknown Title'), 
            "thumbnail": info.get('thumbnail', ''), 
            "formats": sorted_formats
        }

@app.get("/api/download")
def download_video(url: str, height: int, background_tasks: BackgroundTasks):
    file_id = str(uuid.uuid4())
    # Temporary storage before serving to the client
    out_tmpl = f"/tmp/{file_id}.%(ext)s"
    
    # Force highest quality video at the requested height + highest quality audio
    ydl_opts = {
        'format': f'bestvideo[height<={height}]+bestaudio/best',
        'outtmpl': out_tmpl,
        'merge_output_format': 'mp4',
        'quiet': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        
        # yt-dlp automatically forces .mp4 extension on merge
        base, _ = os.path.splitext(filename)
        final_file = f"{base}.mp4"
        
    # Schedule deletion immediately after the transfer completes
    background_tasks.add_task(cleanup, final_file)
    
    clean_title = "".join(c for c in info['title'] if c.isalnum() or c in " -_").strip()
    return FileResponse(
        path=final_file, 
        media_type='video/mp4', 
        filename=f"{clean_title}_{height}p.mp4"
    )
