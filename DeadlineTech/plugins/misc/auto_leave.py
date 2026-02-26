import asyncio
from datetime import datetime, timedelta
from typing import Set

import pytz
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait

import config
from DeadlineTech.utils.database import get_client, is_active_chat
from DeadlineTech.logging import LOGGER

# --- Configuration & Constants ---
LOG = LOGGER(__name__)

# Chats that should never be left (e.g., Logger Group, Support Chat)
EXCLUDED_CHAT_IDS: Set[int] = {
    config.LOGGER_ID, -1001476736723, -1001726765522,  # Fallback if not set
}

MAX_LEAVES_PER_RUN = 50
TIMEZONE = pytz.timezone("Asia/Kolkata")
TARGET_HOUR = 4
TARGET_MINUTE = 35


def get_seconds_until_target() -> float:
    """
    Calculates the number of seconds remaining until the next scheduled run time.
    Default: 4:35 AM IST.
    """
    now = datetime.now(TIMEZONE)
    target = now.replace(
        hour=TARGET_HOUR, 
        minute=TARGET_MINUTE, 
        second=0, 
        microsecond=0
    )
    
    if now >= target:
        target += timedelta(days=1)
    
    return (target - now).total_seconds()


async def leave_inactive_chats(client, client_num: int) -> None:
    """
    Iterates through the client's dialogs and leaves chats deemed inactive.
    
    Args:
        client: The Pyrogram client instance.
        client_num (int): The assistant number identifier.
    """
    left_count = 0
    try:
        async for dialog in client.get_dialogs():
            # Safety break to prevent mass leaving in one go
            if left_count >= MAX_LEAVES_PER_RUN:
                break

            chat = dialog.chat
            
            # Filter: Only consider Groups, Supergroups, and Channels
            if chat.type not in {ChatType.SUPERGROUP, ChatType.GROUP, ChatType.CHANNEL}:
                continue
                
            # Filter: Skip excluded chats
            if chat.id in EXCLUDED_CHAT_IDS:
                continue

            # Check Database for activity
            if not await is_active_chat(chat.id):
                try:
                    await client.leave_chat(chat.id)
                    LOG.info(f"Assistant {client_num} left inactive chat: {chat.title} [{chat.id}]")
                    left_count += 1
                    await asyncio.sleep(1)  # Sleep to avoid hitting limits
                    
                except FloodWait as e:
                    LOG.warning(f"FloodWait of {e.value}s encountered. Skipping...")
                    await asyncio.sleep(e.value)
                except Exception as e:
                    LOG.error(f"Failed to leave chat {chat.title} [{chat.id}]: {e}")
                    
    except Exception as e:
        LOG.error(f"Assistant {client_num} failed to fetch dialogs: {e}")


async def auto_leave_task() -> None:
    """
    Background task that runs daily at a specific time to clean up inactive chats
    from the assistant clients.
    """
    if not config.AUTO_LEAVING_ASSISTANT:
        LOG.info("Auto-Leave Assistant is disabled in config.")
        return

    # Import here to avoid circular dependencies
    from DeadlineTech.core.userbot import assistants

    LOG.info("Auto-Leave task initialized.")

    while True:
        seconds_to_sleep = get_seconds_until_target()
        
        # Log next run time nicely
        next_run = datetime.now(TIMEZONE) + timedelta(seconds=seconds_to_sleep)
        LOG.info(f"Next Auto-Leave scheduled for: {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        await asyncio.sleep(seconds_to_sleep)

        LOG.info("Starting inactive chat cleanup...")
        
        for num in assistants:
            try:
                client = await get_client(num)
                if client:
                    await leave_inactive_chats(client, num)
            except Exception as e:
                LOG.error(f"Error accessing client {num} for cleanup: {e}")
                
        LOG.info("Cleanup cycle completed.")

# Initialize the background task
asyncio.create_task(auto_leave_task())
