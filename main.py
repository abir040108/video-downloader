# language: Python, file: main.py, target: FastAPI / Docker
# *added client spoofing to bypass youtube datacenter ip blocks*
import os
import uuid
from fastapi import FastAPI, BackgroundTasks, HTTPException
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
    # Spoof android/ios clients to evade basic data center IP blocks
    ydl_opts = {
        'quiet': True, 
        'skip_download': True,
        'extractor_args': {'youtube': {'client': ['android', 'ios']}}
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            
            for f in info.get('formats', []):
                if f.get('vcodec') != 'none' and f.get('resolution') and f.get('height'):
                    formats.append({
                        'format_id': f['format_id'],
                        'resolution': f.get('resolution'),
                        'height': f['height'],
                        'ext': f.get('ext')
                    })
            
            unique_formats = {f['height']: f for f in formats}
            sorted_formats = sorted(unique_formats.values(), key=lambda x: x['height'], reverse=True)
            return {
                "title": info.get('title', 'Unknown Title'), 
                "thumbnail": info.get('thumbnail', ''), 
                "formats": sorted_formats
            }
    except Exception as e:
        print(f"Extraction error: {e}")
        raise HTTPException(status_code=400, detail="YouTube blocked the extraction request.")

@app.get("/api/download")
def download_video(url: str, height: int, background_tasks: BackgroundTasks):
    file_id = str(uuid.uuid4())
    out_tmpl = f"/tmp/{file_id}.%(ext)s"
    
    ydl_opts = {
        'format': f'bestvideo[height<={height}]+bestaudio/best',
        'outtmpl': out_tmpl,
        'merge_output_format': 'mp4',
        'quiet': True,
        'extractor_args': {'youtube': {'client': ['android', 'ios']}}
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
        print(f"Download error: {e}")
        raise HTTPException(status_code=400, detail="YouTube blocked the download request.")
