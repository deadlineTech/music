import asyncio
import os
import re
import json
import uuid
import random
import logging
import aiohttp
import aiofiles
import config
import time
import yt_dlp
from pathlib import Path
from urllib.parse import urlparse
from typing import Union, Optional, Dict, Any, List
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType
from youtubesearchpython.__future__ import VideosSearch

from DeadlineTech.utils.database import is_on_off
from DeadlineTech.utils.formatters import time_to_seconds

# === Configuration & Constants ===
YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")

# Client-Side Timeouts
DIRECT_TIMEOUT = 60         # Wait up to 5 minutes for server to respond
TOTAL_RETRIES = 2            # Retry twice if server crashes
CHUNK_SIZE = 1024 * 1024     # 1MB chunks for download

# === Statistics System ===
DOWNLOAD_STATS: Dict[str, int] = {
    "total": 0, "success": 0, "failed": 0,
    "v2_success": 0, "cookie_success": 0,
    "v2_error": 0, "cookie_error": 0
}

def _inc(key: str):
    DOWNLOAD_STATS[key] = DOWNLOAD_STATS.get(key, 0) + 1

def get_stats() -> Dict[str, Any]:
    s = DOWNLOAD_STATS.copy()
    total = s["total"]
    s["success_rate"] = f"{(s['success'] / total) * 100:.2f}%" if total > 0 else "0.00%"
    return s

# === Security & Helpers ===
def is_safe_url(url: str) -> bool:
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"): return False
        allowed = ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com")
        return any(d in p.netloc for d in allowed)
    except: return False

def extract_safe_id(link: str) -> Optional[str]:
    try:
        if "v=" in link: vid = link.split("v=")[-1].split("&")[0]
        elif "youtu.be" in link: vid = link.split("/")[-1].split("?")[0]
        else: return None
        if YOUTUBE_ID_RE.match(vid): return vid
    except: pass
    return None

def cookie_txt_file():
    cookie_dir = f"{os.getcwd()}/cookies"
    if not os.path.exists(cookie_dir): return None
    files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
    return os.path.join(cookie_dir, random.choice(files)) if files else None

# === V2 Direct Logic ===

def _normalize_url(candidate: str) -> Optional[str]:
    api_url = getattr(config, "API_URL", None)
    if not api_url or not candidate: return None
    c = candidate.strip()
    
    # FIX: Remove internal /root/ paths that cause connection resets
    if "/root/" in c or "/home/" in c:
        if "downloads/" in c:
            clean_part = c.split("downloads/")[-1]
            return f"{api_url.rstrip('/')}/media/downloads/{clean_part}"
        return None 

    if c.startswith("http"): return c
    return f"{api_url.rstrip('/')}/{c.lstrip('/')}"

async def _download_cdn(url: str, out_path: str) -> bool:
    print(f"🔗 downloading from CDN: {url}")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    
    for i in range(1, 4): 
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600)) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(1)
                        continue
                    
                    async with aiofiles.open(out_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                            if not chunk: break
                            await f.write(chunk)
            
            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                return True
        except Exception as e:
            print(f"⚠️ CDN Error: {e}")
            await asyncio.sleep(1)
    return False

async def v2_download_process(link: str, video: bool) -> Optional[str]:
    vid = extract_safe_id(link)
    query = vid or link
    ext = "mp4" if video else "m4a"
    out_path = Path("downloads/video" if video else "downloads/audio") / f"{vid or uuid.uuid4().hex[:10]}.{ext}"

    if out_path.exists() and out_path.stat().st_size > 0:
        return str(out_path)

    api_key = getattr(config, "API_KEY", None)
    api_url = getattr(config, "API_URL", None)
    if not api_url or not api_key: return None

    # RETRY LOOP
    for attempt in range(1, TOTAL_RETRIES + 1):
        try:
            print(f"📡 V2 Direct Req {attempt}/{TOTAL_RETRIES} for {query}")
            
            # LONG TIMEOUT REQUEST
            timeout = aiohttp.ClientTimeout(total=DIRECT_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                url = f"{api_url.rstrip('/')}/youtube/v2/download"
                params = {"query": query, "isVideo": str(video).lower(), "api_key": api_key}
                
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        print(f"❌ Server Error: {resp.status}")
                        continue
                    
                    data = await resp.json()

            # Process Response
            if data.get("status") == "success":
                res = data.get("result", {})
                if res.get("success"):
                    # Success! Normalize URL and download
                    raw_url = res.get("public_url")
                    final_url = _normalize_url(raw_url)
                    
                    if final_url and await _download_cdn(final_url, str(out_path)):
                        return str(out_path)
            
            # If server returned success=False or message
            msg = data.get("message") or "Unknown Server Fail"
            print(f"⚠️ API Message: {msg}")

        except asyncio.TimeoutError:
            print(f"⌛ Request Timed Out (> {DIRECT_TIMEOUT}s)")
        except Exception as e:
            print(f"💥 Client Error: {e}")
        
        await asyncio.sleep(1)

    return None


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        return bool(re.search(self.regex, link) and is_safe_url(link))

    async def url(self, message: Message) -> Union[str, None]:
        msgs = [message]
        if message.reply_to_message: msgs.append(message.reply_to_message)
        for msg in msgs:
            text = msg.text or msg.caption or ""
            if not text: continue
            if msg.entities:
                for entity in msg.entities:
                    if entity.type == MessageEntityType.URL:
                        return text[entity.offset:entity.offset+entity.length]
            if msg.caption_entities:
                for entity in msg.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        if not is_safe_url(link): return "Unsafe URL", "0", 0, "", ""

        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration = result["duration"]
            thumb = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            sec = int(time_to_seconds(duration)) if duration else 0
            return title, duration, sec, thumb, vidid
        return None

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        results = VideosSearch(link, limit=1)
        for r in (await results.next())["result"]: return r["title"]
        return ""

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        results = VideosSearch(link, limit=1)
        for r in (await results.next())["result"]: return r["duration"]
        return "00:00"

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        results = VideosSearch(link, limit=1)
        for r in (await results.next())["result"]: return r["thumbnails"][0]["url"].split("?")[0]
        return ""

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if not is_safe_url(link): return 0, "Unsafe URL"

        path = await v2_download_process(link, video=True)
        if path: return 1, path
        
        cookie_file = cookie_txt_file()
        if not cookie_file: return 0, "No cookies"
        
        cmd = ["yt-dlp", "--cookies", cookie_file, "-g", "-f", "best[height<=?720]", "--", link]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if stdout: return 1, stdout.decode().split("\n")[0]
        return 0, stderr.decode()

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid: link = self.listbase + link
        if not is_safe_url(link): return []
        cookie_file = cookie_txt_file()
        if not cookie_file: return []
        cmd = [
            "yt-dlp", "-i", "--get-id", "--flat-playlist", "--cookies", cookie_file,
            "--playlist-end", str(limit), "--skip-download", "--", link
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            if stdout: return [x for x in stdout.decode().split("\n") if x]
        except: pass
        return []

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        results = VideosSearch(link, limit=1)
        for r in (await results.next())["result"]:
            return {
                "title": r["title"], "link": r["link"], "vidid": r["id"],
                "duration_min": r["duration"], "thumb": r["thumbnails"][0]["url"].split("?")[0],
            }, r["id"]
        return None, None

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if not is_safe_url(link): return [], link
        cookie_file = cookie_txt_file()
        if not cookie_file: return [], link
        ytdl_opts = {"quiet": True, "cookiefile": cookie_file}
        out = []
        try:
            with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
                r = ydl.extract_info(link, download=False)
                for f in r.get("formats", []):
                    if "dash" in str(f.get("format")).lower(): continue
                    out.append({
                        "format": f.get("format"), "filesize": f.get("filesize"),
                        "format_id": f.get("format_id"), "ext": f.get("ext"),
                        "format_note": f.get("format_note"), "yturl": link
                    })
        except: pass
        return out, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        if not result or query_type >= len(result): return None
        r = result[query_type]
        return r["title"], r["duration"], r["thumbnails"][0]["url"].split("?")[0], r["id"]

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        _inc("total")
        if videoid: link = self.base + link
        
        if not is_safe_url(link):
            _inc("failed")
            return None, None

        is_vid = True if (video or songvideo) else False
        
        # 1. TRY V2 DIRECT
        path = await v2_download_process(link, video=is_vid)
        if path:
            _inc("success")
            _inc("v2_success")
            return path, True
            
        # 2. LEGACY FALLBACK
        _inc("v2_error")
        cookie_file = cookie_txt_file()
        if not cookie_file:
            _inc("failed")
            return None, None
        
        loop = asyncio.get_running_loop()
        def _legacy_dl():
            opts = {
                "format": "bestaudio/best" if not is_vid else "(bestvideo+bestaudio)",
                "outtmpl": "downloads/%(id)s.%(ext)s", "quiet": True, 
                "cookiefile": cookie_file, "no_warnings": True
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=True)
                return os.path.join("downloads", f"{info['id']}.{info['ext']}")

        try:
            path = await loop.run_in_executor(None, _legacy_dl)
            if path and os.path.exists(path):
                _inc("success")
                _inc("cookie_success")
                return path, True
        except Exception:
            _inc("cookie_error")

        _inc("failed")
        return None, None
