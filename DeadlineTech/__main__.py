# Powered By Team DeadlineTech

import asyncio
import importlib

from pyrogram.types import BotCommand
from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from DeadlineTech import LOGGER, app, userbot
from DeadlineTech.core.call import damian
from DeadlineTech.misc import sudo
from DeadlineTech.plugins import ALL_MODULES
from DeadlineTech.utils.database import get_banned_users, get_gbanned
from DeadlineTech.utils.crash_reporter import setup_global_exception_handler
from config import BANNED_USERS

async def init():
    # ✅ Enable global crash handler
    setup_global_exception_handler()

  
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        exit()
    await sudo()
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass
    await app.start()

    await app.set_bot_commands([
        BotCommand("start", "Sᴛᴀʀᴛ's Tʜᴇ Bᴏᴛ"), 
        BotCommand("ping", "Cʜᴇᴄᴋ ɪғ ʙᴏᴛ ɪs ᴀʟɪᴠᴇ"),
        BotCommand("help", "Gᴇᴛ Cᴏᴍᴍᴀɴᴅs Lɪsᴛ"),
        BotCommand("music", "download the songs 🎵"), 
        BotCommand("play", "Pʟᴀʏ Mᴜsɪᴄ ɪɴ Vᴄ"),
        BotCommand("vplay", "starts Streaming the requested Video Song"), 
        BotCommand("playforce", "forces to play your requested song"), 
        BotCommand("vplayforce", "forces to play your requested Video song"), 
        BotCommand("pause", "pause the current playing stream"), 
        BotCommand("resume", "resume the paused stream"), 
        BotCommand("skip", "skip the current playing stream"), 
        BotCommand("end", "end the current stream"), 
        BotCommand("player", "get a interactive player panel"), 
        BotCommand("queue", "shows the queued tracks list"), 
        BotCommand("auth", "add a user to auth list"), 
        BotCommand("unauth", "remove a user from the auth list"), 
        BotCommand("authusers", "shows the list of the auth users"), 
        BotCommand("cplay", "starts streaming the requested audio on channel"), 
        BotCommand("cvplay", "Starts Streaming the video track on channel"), 
        BotCommand("channelplay", "connect channel to a group and start streaming"), 
        BotCommand("shuffle", "shuffle's the queue"), 
        BotCommand("seek", "seek the stream to the given duration"), 
        BotCommand("seekback", "backward seek the stream"), 
        BotCommand("speed", "for adjusting the audio playback speed"), 
        BotCommand("loop", "enables the loop for the given value")
    ])

    
    for all_module in ALL_MODULES:
        importlib.import_module("DeadlineTech.plugins" + all_module)
    LOGGER("DeadlineTech.plugins").info("Successfully Imported Modules...")
    await userbot.start()
    await damian.start()
    try:
        await damian.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4")
    except NoActiveGroupCall:
        LOGGER("DeadlineTech").error(
            "Please turn on the videochat of your log group\channel.\n\nStopping Bot..."
        )
        exit()
    except:
        pass
    await damian.decorators()
    LOGGER("DeadlineTech").info(
        "DeadlineTech Music Bot started successfully"
    )
    await idle()
    await app.stop()
    await userbot.stop()
    LOGGER("DeadlineTech").info("Stopping DeadlineTech Music Bot...")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
