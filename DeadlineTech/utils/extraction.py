from pyrogram.enums import MessageEntityType
from pyrogram.types import Message, User

from DeadlineTech import app


async def extract_user(m: Message) -> User:
    # Check for reply first
    if m.reply_to_message:
        return m.reply_to_message.from_user
    
    # Safely get entity with bounds checking
    entities = m.entities or []
    if not entities:
        raise ValueError("No user specified. Reply to a user or use /command @username/user_id")
    
    # Get the appropriate entity index
    entity_idx = 1 if m.text.startswith("/") else 0
    if entity_idx >= len(entities):
        entity_idx = 0  # Fallback to first entity
    
    msg_entities = entities[entity_idx]
    
    # Safely get command argument
    command_arg = m.command[1] if len(m.command) > 1 else None
    
    if msg_entities.type == MessageEntityType.TEXT_MENTION:
        return await app.get_users(msg_entities.user.id)
    elif command_arg:
        if command_arg.isdecimal():
            return await app.get_users(int(command_arg))
        else:
            return await app.get_users(command_arg)
    else:
        raise ValueError("No user specified. Reply to a user or use /command @username/user_id")
