# Powered By Team DeadlineTech

import asyncio
import importlib

from pyrogram.types import BotCommand
from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from DeadlineTech import LOGGER, app, userbot
from DeadlineTech.core.call import Anony
from DeadlineTech.misc import sudo, dbb, heroku
from DeadlineTech.plugins import ALL_MODULES

# Import background task starters (they don't start tasks at import time anymore)
from DeadlineTech.plugins.broadcast import start_broadcast_tasks
from DeadlineTech.plugins.seeker import start_timer_task
from DeadlineTech.plugins.auto_leave import start_auto_leave_task

async def init():

    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        exit()
    
    # Initialize local DB and Heroku connection
    dbb()
    heroku()
    
    await sudo()
    
    await app.start()

    # Updated commands list: Removed clone/music, added playlist commands
    await app.set_bot_commands([
        BotCommand("start", "Sᴛᴀʀᴛ's Tʜᴇ Bᴏᴛ"),
        BotCommand("ping", "Cʜᴇᴄᴋ ɪғ ʙᴏᴛ ɪs ᴀʟɪᴠᴇ"),
        BotCommand("help", "Gᴇᴛ Cᴏᴍᴍᴀɴᴅs Lɪsᴛ"),
        BotCommand("play", "Pʟᴀʏ Mᴜsɪᴄ ɪɴ Vᴄ"),
        BotCommand("vplay", "starts Streaming the requested Video Song"), 
        BotCommand("playforce", "forces to play your requested song"), 
        BotCommand("vplayforce", "forces to play your requested Video song"), 
        BotCommand("playlist", "Manage your personal saved playlists"), 
        BotCommand("playlists", "View all your saved folders"), 
        BotCommand("del_playlist", "Delete a saved playlist"), 
        BotCommand("pause", "pause the current playing stream"), 
        BotCommand("resume", "resume the paused stream"), 
        BotCommand("skip", "skip the current playing stream"), 
        BotCommand("end", "end the current stream"), 
        BotCommand("player", "get a interactive player panel"), 
        BotCommand("queue", "shows the queued tracks list"), 
        BotCommand("auth", "add a user to auth list"), 
        BotCommand("unauth", "remove a user from the auth list"), 
        BotCommand("authusers", "shows the list of the auth users"), 
        BotCommand("shuffle", "shuffle's the queue"), 
        BotCommand("seek", "seek the stream to the given duration"), 
        BotCommand("seekback", "backward seek the stream"), 
        BotCommand("speed", "for adjusting the audio playback speed"), 
        BotCommand("loop", "enables the loop for the given value"),
        BotCommand("reboot", "Reboot bot for individual chat")
    ])

    for all_module in ALL_MODULES:
        importlib.import_module("DeadlineTech.plugins." + all_module)
    LOGGER("DeadlineTech.plugins").info("Plugins Imported Successfully...")
    
    LOGGER("DeadlineTech").info("Starting background tasks...")
    start_broadcast_tasks()
    start_timer_task()
    start_auto_leave_task()
    LOGGER("DeadlineTech").info("Background tasks started successfully")
    
    await userbot.start()
    await Anony.start()
    try:
        await Anony.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4")
    except NoActiveGroupCall:
        LOGGER("DeadlineTech").error(
            "turn on the videochat of your log group."
        )
        exit()
    except:
        pass
    await Anony.decorators()
    LOGGER("DeadlineTech").info(
        "DeadlineTech Music Bot started successfully"
    )
    await idle()
    await app.stop()
    await userbot.stop()
    LOGGER("DeadlineTech").info("Stopping DeadlineTech Music Bot...")

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
