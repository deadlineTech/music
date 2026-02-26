# ==========================================================
# 🎧 Public Open-Source VC Player Music Bot (Cookies Based)
# 🛠️ Maintained by Team DeadlineTech | Lead Developer: @Its_damiann
# 🔓 Licensed for Public Use — All Rights Reserved © Team DeadlineTech
# ❤️ Openly built for the community, but proudly protected by the passion of its creators.
# ==========================================================

import asyncio
import os
from datetime import datetime, timedelta
from typing import Union

from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls
from pytgcalls.exceptions import NoActiveGroupCall
from ntgcalls import (
    ConnectionNotFound, 
    TelegramServerError, 
    RTMPStreamingUnsupported, 
    ConnectionError
)
from pytgcalls.types import Update, MediaStream, AudioQuality, VideoQuality

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

class Call(PyTgCalls):
    def __init__(self):
        self.userbot1 = Client(
            name="DeadlineXAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
        )
        self.one = PyTgCalls(self.userbot1, cache_duration=100)
        
        self.userbot2 = Client(
            name="DeadlineXAss2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
        )
        self.two = PyTgCalls(self.userbot2, cache_duration=100)
        
        self.userbot3 = Client(
            name="DeadlineXAss3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
        )
        self.three = PyTgCalls(self.userbot3, cache_duration=100)
        
        self.userbot4 = Client(
            name="DeadlineXAss4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
        )
        self.four = PyTgCalls(self.userbot4, cache_duration=100)
        
        self.userbot5 = Client(
            name="DeadlineXAss5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
        )
        self.five = PyTgCalls(self.userbot5, cache_duration=100)

    async def pause_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.pause(chat_id)

    async def resume_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)

    async def stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            await _clear_(chat_id)
            await assistant.leave_call(chat_id)
        except:
            pass

    async def stop_stream_force(self, chat_id: int):
        for client in [self.one, self.two, self.three, self.four, self.five]:
            try:
                if getattr(config, f"STRING{list([self.one, self.two, self.three, self.four, self.five]).index(client) + 1}"):
                    await client.leave_call(chat_id)
            except:
                pass
        try:
            await _clear_(chat_id)
        except:
            pass

    async def speedup_stream(self, chat_id: int, file_path, speed, playing):
        assistant = await group_assistant(self, chat_id)
        if str(speed) != str("1.0"):
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            if not os.path.isdir(chatdir):
                os.makedirs(chatdir)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                vs = {
                    "0.5": 2.0,
                    "0.75": 1.35,
                    "1.5": 0.68,
                    "2.0": 0.5
                }.get(str(speed), 1.0)
                
                proc = await asyncio.create_subprocess_shell(
                    cmd=(
                        "ffmpeg "
                        "-i "
                        f"{file_path} "
                        "-filter:v "
                        f"setpts={vs}*PTS "
                        "-filter:a "
                        f"atempo={speed} "
                        f"{out}"
                    ),
                    stdin=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
            else:
                pass
        else:
            out = file_path
            
        dur = await asyncio.get_event_loop().run_in_executor(None, check_duration, out)
        dur = int(dur)
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration = seconds_to_min(dur)
        
        stream_params = {
            "media_path": out,
            "audio_parameters": AudioQuality.HIGH,
            "ffmpeg_parameters": f"-ss {played} -to {duration}"
        }
        if playing[0]["streamtype"] == "video":
            stream_params["video_parameters"] = VideoQuality.HD_720p

        stream = MediaStream(**stream_params)

        if str(db[chat_id][0]["file"]) == str(file_path):
            await assistant.play(chat_id, stream)
        else:
            raise AssistantErr("Umm")
            
        if str(db[chat_id][0]["file"]) == str(file_path):
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
            check.pop(0)
        except:
            pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        try:
            await assistant.leave_call(chat_id)
        except:
            pass

    async def skip_stream(
        self,
        chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        stream_params = {
            "media_path": link,
            "audio_parameters": AudioQuality.HIGH,
        }
        if video:
            stream_params["video_parameters"] = VideoQuality.HD_720p
            
        stream = MediaStream(**stream_params)
        await assistant.play(chat_id, stream)

    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistant = await group_assistant(self, chat_id)
        stream_params = {
            "media_path": file_path,
            "audio_parameters": AudioQuality.HIGH,
            "ffmpeg_parameters": f"-ss {to_seek} -to {duration}"
        }
        if mode == "video":
            stream_params["video_parameters"] = VideoQuality.HD_720p
            
        stream = MediaStream(**stream_params)
        await assistant.play(chat_id, stream)

    async def stream_call(self, link):
        assistant = await group_assistant(self, config.LOGGER_ID)
        await assistant.play(
            config.LOGGER_ID,
            MediaStream(media_path=link, audio_parameters=AudioQuality.HIGH)
        )
        await asyncio.sleep(0.2)
        await assistant.leave_call(config.LOGGER_ID)

    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        language = await get_lang(chat_id)
        _ = get_string(language)
        
        stream_params = {
            "media_path": link,
            "audio_parameters": AudioQuality.HIGH,
        }
        if video:
            stream_params["video_parameters"] = VideoQuality.HD_720p

        stream = MediaStream(**stream_params)
        try:
            await assistant.play(chat_id, stream)
        except NoActiveGroupCall:
            raise AssistantErr(_["call_8"])
        except ConnectionError:
            raise AssistantErr(_["call_9"])
        except TelegramServerError:
            raise AssistantErr(_["call_10"])
            
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)
        if await is_autoend():
            counter[chat_id] = {}
            try:
                users = len(await assistant.get_participants(chat_id))
                if users == 1:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
            except:
                pass

    async def change_stream(self, client, chat_id):
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                popped = check.pop(0)
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
            except:
                return
        else:
            queued = check[0]["file"]
            language = await get_lang(chat_id)
            _ = get_string(language)
            title = (check[0]["title"]).title()
            user = check[0]["by"]
            original_chat_id = check[0]["chat_id"]
            streamtype = check[0]["streamtype"]
            videoid = check[0]["vidid"]
            db[chat_id][0]["played"] = 0
            exis = (check[0]).get("old_dur")
            if exis:
                db[chat_id][0]["dur"] = exis
                db[chat_id][0]["seconds"] = check[0]["old_second"]
                db[chat_id][0]["speed_path"] = None
                db[chat_id][0]["speed"] = 1.0
            video = True if str(streamtype) == "video" else False
            
            stream_params = {
                "audio_parameters": AudioQuality.HIGH,
            }
            if video:
                stream_params["video_parameters"] = VideoQuality.HD_720p

            if "live_" in queued:
                n, link = await YouTube.video(videoid, True)
                if n == 0:
                    return await app.send_message(original_chat_id, text=_["call_6"])
                stream_params["media_path"] = link
                stream = MediaStream(**stream_params)
                
                try:
                    await client.play(chat_id, stream)
                except Exception:
                    return await app.send_message(original_chat_id, text=_["call_6"])
                    
                button = stream_markup(_, chat_id)
                run = await app.send_message(
                    chat_id=original_chat_id,
                    text=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
                
            elif "vid_" in queued:
                mystic = await app.send_message(original_chat_id, _["call_7"])
                try:
                    file_path, direct = await YouTube.download(
                        videoid,
                        mystic,
                        videoid=True,
                        video=video,
                    )
                except:
                    return await mystic.edit_text(_["call_6"], disable_web_page_preview=True)
                    
                stream_params["media_path"] = file_path
                stream = MediaStream(**stream_params)
                
                try:
                    await client.play(chat_id, stream)
                except:
                    return await app.send_message(original_chat_id, text=_["call_6"])
                    
                button = stream_markup(_, chat_id)
                await mystic.delete()
                run = await app.send_message(
                    chat_id=original_chat_id,
                    text=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
                
            elif "index_" in queued:
                stream_params["media_path"] = videoid
                stream = MediaStream(**stream_params)
                try:
                    await client.play(chat_id, stream)
                except:
                    return await app.send_message(original_chat_id, text=_["call_6"])
                button = stream_markup(_, chat_id)
                run = await app.send_message(
                    chat_id=original_chat_id,
                    text=_["stream_2"].format(user),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
                
            else:
                stream_params["media_path"] = queued
                stream = MediaStream(**stream_params)
                try:
                    await client.play(chat_id, stream)
                except:
                    return await app.send_message(original_chat_id, text=_["call_6"])
                
                button = stream_markup(_, chat_id)
                if videoid == "telegram":
                    run = await app.send_message(
                        chat_id=original_chat_id,
                        text=_["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
                elif videoid == "soundcloud":
                    run = await app.send_message(
                        chat_id=original_chat_id,
                        text=_["stream_1"].format(config.SUPPORT_CHAT, title[:23], check[0]["dur"], user),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"
                else:
                    run = await app.send_message(
                        chat_id=original_chat_id,
                        text=_["stream_1"].format(
                            f"https://t.me/{app.username}?start=info_{videoid}",
                            title[:23],
                            check[0]["dur"],
                            user,
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"

    async def ping(self):
        pings = []
        if config.STRING1:
            pings.append(await self.one.ping)
        if config.STRING2:
            pings.append(await self.two.ping)
        if config.STRING3:
            pings.append(await self.three.ping)
        if config.STRING4:
            pings.append(await self.four.ping)
        if config.STRING5:
            pings.append(await self.five.ping)
        return str(round(sum(pings) / len(pings), 3))

    async def start(self):
        LOGGER(__name__).info("Starting PyTgCalls Client...\n")
        if config.STRING1:
            await self.one.start()
        if config.STRING2:
            await self.two.start()
        if config.STRING3:
            await self.three.start()
        if config.STRING4:
            await self.four.start()
        if config.STRING5:
            await self.five.start()

    async def decorators(self):
        @self.one.on_stream_end()
        @self.two.on_stream_end()
        @self.three.on_stream_end()
        @self.four.on_stream_end()
        @self.five.on_stream_end()
        async def stream_end_handler(client, update: Update):
            await self.change_stream(client, update.chat_id)

Anony = Call()
