# Powered By Team DeadlineTech

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyrogram.enums import ChatType

from DeadlineTech import app
from DeadlineTech.utils.database import (
    get_user_playlists, set_active_playlist, create_new_playlist, 
    delete_user_playlist, remove_track_by_index
)
from config import BANNED_USERS

# ==========================================
# 1. MANAGEMENT COMMANDS
# ==========================================

@app.on_message(filters.command(["playlists", "playlist"]) & filters.private & ~BANNED_USERS)
async def manage_playlists(client, message: Message):
    user_id = message.from_user.id
    data = await get_user_playlists(user_id)
    playlists = data["playlists"]
    active = data["active"]
    
    if not playlists:
        return await message.reply_text("❌ You don't have any playlists. Click ➕ on a playing song to start!")
        
    buttons = []
    for name in playlists.keys():
        display = f"⭐ {name}" if name == active else f"📁 {name}"
        buttons.append([
            InlineKeyboardButton(text=f"{display} ({len(playlists[name])}/25)", callback_data=f"pl_view|{name}")
        ])
    
    if len(playlists) < 5:
        buttons.append([InlineKeyboardButton(text="➕ Create Folder", callback_data="pl_create_prompt")])
    buttons.append([InlineKeyboardButton(text="🗑 Close", callback_data="close")])
        
    await message.reply_text(
        f"<b>📚 Your Library:</b>\nClick a folder to view songs or edit details. Folders with ⭐ are 'Active'.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_message(filters.command("del_playlist") & filters.private & ~BANNED_USERS)
async def del_playlist_cmd(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/del_playlist FolderName`")
    
    name = message.text.split(None, 1)[1].strip()
    deleted = await delete_user_playlist(message.from_user.id, name)
    if deleted:
        await message.reply_text(f"✅ Playlist <code>{name}</code> deleted.")
    else:
        await message.reply_text("❌ Playlist not found.")

# ==========================================
# 2. EDITING & NAVIGATION CALLBACKS
# ==========================================

@app.on_callback_query(filters.regex(r"^pl_view\|") & ~BANNED_USERS)
async def pl_view_cb(client, CallbackQuery):
    name = CallbackQuery.data.split("|")[1]
    user_id = CallbackQuery.from_user.id
    data = await get_user_playlists(user_id)
    playlists = data["playlists"]
    
    if name not in playlists:
        return await CallbackQuery.answer("❌ Folder not found.", show_alert=True)
    
    songs = playlists[name]
    text = f"<b>📁 Folder: {name}</b>\n\n"
    if not songs:
        text += "_This folder is empty._"
    else:
        for i, song in enumerate(songs, 1):
            text += f"<b>{i}.</b> {song['title'][:45]}\n"
            
    buttons = [
        [InlineKeyboardButton(text="✏️ Remove Tracks", callback_data=f"pl_edit|{name}")],
        [InlineKeyboardButton(text="⭐ Set as Active", callback_data=f"pl_active|{name}")],
        [InlineKeyboardButton(text="🗑 Delete Folder", callback_data=f"pl_del|{name}")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="pl_home")]
    ]
    await CallbackQuery.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"^pl_edit\|") & ~BANNED_USERS)
async def pl_edit_cb(client, CallbackQuery):
    name = CallbackQuery.data.split("|")[1]
    data = await get_user_playlists(CallbackQuery.from_user.id)
    songs = data["playlists"].get(name, [])
    
    text = f"<b>🛠 Editing: {name}</b>\nSelect a track number to remove it:\n\n"
    buttons = []
    row = []
    for i, _ in enumerate(songs, 1):
        row.append(InlineKeyboardButton(text=f"🗑 {i}", callback_data=f"pl_rem_track|{name}|{i-1}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data=f"pl_view|{name}")])
    
    await CallbackQuery.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"^pl_active\|") & ~BANNED_USERS)
async def pl_active_cb(client, CallbackQuery):
    name = CallbackQuery.data.split("|")[1]
    await set_active_playlist(CallbackQuery.from_user.id, name)
    await CallbackQuery.answer(f"✅ '{name}' is now your Active folder for saving!", show_alert=True)
    await pl_view_cb(client, CallbackQuery)
