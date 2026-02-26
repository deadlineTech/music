# DeadlineTech/core/call.py
import asyncio
import os
from datetime import datetime, timedelta
from typing import Union

from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality, Update
from pytgcalls.exceptions import (
    AlreadyJoinedError,
    NoActiveGroupCall,
    TelegramServerError,
)

import config
from DeadlineTech import LOGGER, YouTube, app
from DeadlineTech.misc import db
from DeadlineTech.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_autoend,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from DeadlineTech.utils.exceptions import AssistantErr
from DeadlineTech.utils.formatters import check_duration, seconds_to_min, speed_converter
from DeadlineTech.utils.inline.play import stream_markup
from DeadlineTech.utils.stream.autoclear import auto_clean
from strings import get_string

autoend = {}
counter = {}

async def _clear_(chat_id):
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)

class Call:
    def __init__(self):
        self.userbot1 = Client(
            name="DeadlineXAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
        )
        self.one = PyTgCalls(self.userbot1)
        
        self.userbot2 = Client(
            name="DeadlineXAss2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
        )
        self.two = PyTgCalls(self.userbot2)
        
        self.userbot3 = Client(
            name="DeadlineXAss3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
        )
        self.three = PyTgCalls(self.userbot3)
        
        self.userbot4 = Client(
            name="DeadlineXAss4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
        )
        self.four = PyTgCalls(self.userbot4)
        
        self.userbot5 = Client(
            name="DeadlineXAss5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
        )
        self.five = PyTgCalls(self.userbot5)

    async def pause_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.pause_stream(chat_id)

    async def resume_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.resume_stream(chat_id)

    async def stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            await _clear_(chat_id)
            await assistant.leave_call(chat_id)
        except:
            pass

    async def stop_stream_force(self, chat_id: int):
        for call_client in [self.one, self.two, self.three, self.four, self.five]:
            try:
                await call_client.leave_call(chat_id)
            except:
                pass
        try:
            await _clear_(chat_id)
        except:
            pass

    async def speedup_stream(self, chat_id: int, file_path, speed, playing):
        assistant = await group_assistant(self, chat_id)
        if str(speed) != "1.0":
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            os.makedirs(chatdir, exist_ok=True)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                vs = {"0.5": 2.0, "0.75": 1.35, "1.5": 0.68, "2.0": 0.5}.get(str(speed), 1.0)
                proc = await asyncio.create_subprocess_shell(
                    f"ffmpeg -i {file_path} -filter:v setpts={vs}*PTS -filter:a atempo={speed} {out}",
                    stdin=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
        else:
            out = file_path

        dur = await asyncio.get_event_loop().run_in_executor(None, check_duration, out)
        dur = int(dur)
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration = seconds_to_min(dur)
        
        stream = MediaStream(
            out,
            audio_parameters=AudioQuality.HIGH,
            video_flags=MediaStream.Flags.VIDEO if playing[0]["streamtype"] == "video" else MediaStream.Flags.IGNORE,
            video_parameters=VideoQuality.MEDIUM if playing[0]["streamtype"] == "video" else None,
            ffmpeg_parameters=f"-ss {played} -to {duration}"
        )

        if str(db[chat_id][0]["file"]) == str(file_path):
            await assistant.play(chat_id, stream)
        else:
            raise AssistantErr("Umm")
            
        exis = (playing[0]).get("old_dur")
        if not exis:
            db[chat_id][0]["old_dur"] = db[chat_id][0]["dur"]
            db[chat_id][0]["old_second"] = db[chat_id][0]["seconds"]
        db[chat_id][0]["played"] = con_seconds
        db[chat_id][0]["dur"] = duration
        db[chat_id][0]["seconds"] = dur
        db[chat_id][0]["speed_path"] = out
        db[chat_id][0]["speed"] = speed

    async def force_stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            check = db.get(chat_id)
            if check: check.pop(0)
        except: pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        try: await assistant.leave_call(chat_id)
        except: pass

    async def join_call(self, chat_id: int, original_chat_id: int, link, video: Union[bool, str] = None):
        assistant = await group_assistant(self, chat_id)
        language = await get_lang(chat_id)
        _ = get_string(language)
        
        stream = MediaStream(
            link,
            audio_parameters=AudioQuality.HIGH,
            video_flags=MediaStream.Flags.VIDEO if video else MediaStream.Flags.IGNORE,
            video_parameters=VideoQuality.MEDIUM if video else None
        )
        
        try:
            await assistant.play(chat_id, stream)
        except NoActiveGroupCall:
            raise AssistantErr(_["call_8"])
        except AlreadyJoinedError:
            raise AssistantErr(_["call_9"])
        except TelegramServerError:
            raise AssistantErr(_["call_10"])
            
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video: await add_active_video_chat(chat_id)

    async def change_stream(self, client, chat_id):
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0: popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            await auto_clean(popped)
            if not check:
                await _clear_(chat_id)
                return await client.leave_call(chat_id)
        except:
            try:
                await _clear_(chat_id)
                return await client.leave_call(chat_id)
            except: return
            
        queued = check[0]["file"]
        language = await get_lang(chat_id)
        _ = get_string(language)
        title = (check[0]["title"]).title()
        user = check[0]["by"]
        original_chat_id = check[0]["chat_id"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]
        db[chat_id][0]["played"] = 0
        video = True if str(streamtype) == "video" else False
        
        link = queued
        if "live_" in queued or "vid_" in queued:
            mystic = await app.send_message(original_chat_id, _["call_7"])
            try:
                file_path, direct = await YouTube.download(videoid, mystic, videoid=True, video=video)
                link = file_path
                await mystic.delete()
            except:
                return await mystic.edit_text(_["call_6"])

        stream = MediaStream(
            link,
            audio_parameters=AudioQuality.HIGH,
            video_flags=MediaStream.Flags.VIDEO if video else MediaStream.Flags.IGNORE,
            video_parameters=VideoQuality.MEDIUM if video else None
        )
        try:
            await client.play(chat_id, stream)
        except:
            return await app.send_message(original_chat_id, text=_["call_6"])

        button = stream_markup(_, chat_id)
        run = await app.send_message(
            chat_id=original_chat_id,
            text=_["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                str(title)[:23],
                str(check[0]["dur"]),
                str(user),
            ),
            reply_markup=InlineKeyboardMarkup(button),
        )
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "stream"

    async def stream_call(self, link):
        assistant = await group_assistant(self, config.LOGGER_ID)
        await assistant.play(config.LOGGER_ID, MediaStream(link))
        await asyncio.sleep(0.2)
        await assistant.leave_call(config.LOGGER_ID)

    async def start(self):
        LOGGER(__name__).info("Starting PyTgCalls Client...\n")
        if config.STRING1: await self.one.start()
        if config.STRING2: await self.two.start()
        if config.STRING3: await self.three.start()
        if config.STRING4: await self.four.start()
        if config.STRING5: await self.five.start()

    async def decorators(self):
        @self.one.on_stream_end()
        @self.two.on_stream_end()
        @self.three.on_stream_end()
        @self.four.on_stream_end()
        @self.five.on_stream_end()
        async def stream_end_handler1(client, update: Update):
            await self.change_stream(client, update.chat_id)
            
        @self.one.on_closed_voice_chat()
        @self.two.on_closed_voice_chat()
        @self.three.on_closed_voice_chat()
        @self.four.on_closed_voice_chat()
        @self.five.on_closed_voice_chat()
        @self.one.on_kicked()
        @self.two.on_kicked()
        @self.three.on_kicked()
        @self.four.on_kicked()
        @self.five.on_kicked()
        @self.one.on_left()
        @self.two.on_left()
        @self.three.on_left()
        @self.four.on_left()
        @self.five.on_left()
        async def stream_services_handler(_, chat_id: int):
            await self.stop_stream(chat_id)

Anony = Call()
