# Powered By Team DeadlineTech

import asyncio

from DeadlineTech.misc import db
from DeadlineTech.utils.database import get_active_chats, is_music_playing


async def timer():
    while not await asyncio.sleep(1):
        try:
            active_chats = await get_active_chats()
            for chat_id in active_chats:
                if not await is_music_playing(chat_id):
                    continue
                playing = db.get(chat_id)
                if not playing:
                    continue
                duration = int(playing[0]["seconds"])
                if duration == 0:
                    continue
                if db[chat_id][0]["played"] >= duration:
                    continue
                db[chat_id][0]["played"] += 1
        except Exception:
            # Prevent task from dying on errors
            continue


# Task will be started from __main__.py after event loop is ready
# DO NOT create task at module level - it causes event loop issues
def start_timer_task():
    """Call this function to start the timer task after event loop is ready."""
    asyncio.create_task(timer())
