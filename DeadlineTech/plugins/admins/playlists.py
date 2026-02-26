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

@app.on_message(filters.command(["playlists", "playlist"]) & ~BANNED_USERS)
async def manage_playlists(client, message: Message):
    user_id = message.from_user.id
    data = await get_user_playlists(user_id)
    playlists = data["playlists"]
    active = data["active"]
    
    buttons = []
    if playlists:
        for name in playlists.keys():
            display = f"⭐ {name}" if name == active else f"📁 {name}"
            buttons.append([
                InlineKeyboardButton(text=f"{display} ({len(playlists[name])}/25)", callback_data=f"pl_view|{name}")
            ])
    
    if len(playlists) < 5:
        buttons.append([InlineKeyboardButton(text="➕ Create New Folder", callback_data="pl_create_new")])
        
    buttons.append([InlineKeyboardButton(text="🗑 Close", callback_data="close")])
        
    text = "<b>📚 Your Music Library:</b>\n\n"
    if not playlists:
        text += "<i>You don't have any playlists yet. Click below to create one, or simply click '❤️ Save' on any playing song!</i>"
    else:
        text += "Click a folder below to view its songs or edit its details. Folders marked with ⭐ are your 'Active' save destination.\n\n"
        text += "<b>💡 How to Play:</b>\n"
        text += "To stream a playlist in voice chat, tap to copy its command below:\n\n"
        for name in playlists.keys():
            text += f"➥ <code>/play {name}</code>\n"

    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_message(filters.command("del_playlist") & ~BANNED_USERS)
async def del_playlist_cmd(client, message: Message):
    if message.chat.type != ChatType.PRIVATE:
        return await message.reply_text("⚠️ Please use this command in my Private Chat to delete folders.")
    
    if len(message.command) < 2:
        return await message.reply_text("Usage: <code>/del_playlist FolderName</code>")
    
    name = message.text.split(None, 1)[1].strip()
    deleted = await delete_user_playlist(message.from_user.id, name)
    if deleted:
        await message.reply_text(f"✅ Playlist <code>{name}</code> has been successfully deleted.")
    else:
        await message.reply_text("❌ Playlist not found. Please double check the name.")

@app.on_callback_query(filters.regex(r"^pl_home") & ~BANNED_USERS)
async def pl_home_cb(client, CallbackQuery):
    user_id = CallbackQuery.from_user.id
    data = await get_user_playlists(user_id)
    playlists = data["playlists"]
    active = data["active"]
    
    buttons = []
    if playlists:
        for name in playlists.keys():
            display = f"⭐ {name}" if name == active else f"📁 {name}"
            buttons.append([
                InlineKeyboardButton(text=f"{display} ({len(playlists[name])}/25)", callback_data=f"pl_view|{name}")
            ])
            
    if len(playlists) < 5:
        buttons.append([InlineKeyboardButton(text="➕ Create New Folder", callback_data="pl_create_new")])
        
    buttons.append([InlineKeyboardButton(text="🗑 Close", callback_data="close")])
    
    text = "<b>📚 Your Music Library:</b>\n\n"
    if not playlists:
        text += "<i>You don't have any playlists yet. Click below to create one!</i>"
    else:
        text += "Click a folder below to view its songs or edit its details. Folders marked with ⭐ are your 'Active' save destination.\n\n"
        text += "<b>💡 How to Play:</b>\n"
        text += "To stream a playlist in voice chat, tap to copy its command below:\n\n"
        for name in playlists.keys():
            text += f"➥ <code>/play {name}</code>\n"

    await CallbackQuery.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"^pl_create_new") & ~BANNED_USERS)
async def pl_create_new_cb(client, CallbackQuery):
    user_id = CallbackQuery.from_user.id
    data = await get_user_playlists(user_id)
    playlists = data["playlists"]
    
    if len(playlists) >= 5:
        return await CallbackQuery.answer("❌ You have reached the limit of 5 playlists.", show_alert=True)
        
    # Auto-generate a unique MusicXXXX name
    while True:
        new_name = f"Music{random.randint(1000, 9999)}"
        if new_name not in playlists:
            break
    
    await create_new_playlist(user_id, new_name)
    
    # Automatically set the newly created playlist as active if it's their only one
    if len(playlists) == 0:
        await set_active_playlist(user_id, new_name)
        
    await CallbackQuery.answer(f"✅ Created '{new_name}' successfully!", show_alert=True)
    await pl_home_cb(client, CallbackQuery)

@app.on_callback_query(filters.regex(r"^pl_view\|") & ~BANNED_USERS)
async def pl_view_cb(client, CallbackQuery):
    name = CallbackQuery.data.split("|")[1]
    user_id = CallbackQuery.from_user.id
    data = await get_user_playlists(user_id)
    playlists = data["playlists"]
    active = data["active"]
    
    if name not in playlists:
        return await CallbackQuery.answer("❌ Folder not found.", show_alert=True)
    
    songs = playlists[name]
    text = f"<b>📁 Folder:</b> <code>{name}</code> "
    text += "(⭐ Active)\n" if name == active else "\n"
    text += f"<b>▶️ Command:</b> <code>/play {name}</code>\n\n"
    
    if not songs:
        text += "<i>This folder is empty.</i>"
    else:
        for i, song in enumerate(songs, 1):
            title = song['title'][:45] + "..." if len(song['title']) > 45 else song['title']
            text += f"<b>{i}.</b> {title}\n"
            
    buttons = []
    if songs:
        buttons.append([InlineKeyboardButton(text="✏️ Edit (Remove Tracks)", callback_data=f"pl_edit|{name}")])
        
    if name != active:
        buttons.append([InlineKeyboardButton(text="⭐ Set as Active", callback_data=f"pl_active|{name}")])
        
    buttons.append([
        InlineKeyboardButton(text="🗑 Delete Folder", callback_data=f"pl_del|{name}"),
        InlineKeyboardButton(text="🔙 Back", callback_data="pl_home")
    ])
    
    await CallbackQuery.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"^pl_active\|") & ~BANNED_USERS)
async def pl_active_cb(client, CallbackQuery):
    name = CallbackQuery.data.split("|")[1]
    await set_active_playlist(CallbackQuery.from_user.id, name)
    await CallbackQuery.answer(f"✅ '{name}' is now your Active folder for saving!", show_alert=True)
    await pl_view_cb(client, CallbackQuery)

@app.on_callback_query(filters.regex(r"^pl_edit\|") & ~BANNED_USERS)
async def pl_edit_cb(client, CallbackQuery):
    # Rule: Removal only in PM
    if CallbackQuery.message.chat.type != ChatType.PRIVATE:
        return await CallbackQuery.answer(
            "⚠️ You can only remove tracks in my Private Chat!", 
            show_alert=True, 
            url=f"https://t.me/{app.username}?start=playlist"
        )

    name = CallbackQuery.data.split("|")[1]
    data = await get_user_playlists(CallbackQuery.from_user.id)
    songs = data["playlists"].get(name, [])
    
    if not songs:
        return await CallbackQuery.answer("❌ This playlist is empty.", show_alert=True)
    
    text = f"<b>🛠 Editing:</b> <code>{name}</code>\nSelect a track number below to remove it from this folder:\n\n"
    buttons = []
    row = []
    for i, song in enumerate(songs, 1):
        title = song['title'][:35] + "..." if len(song['title']) > 35 else song['title']
        text += f"<b>{i}.</b> {title}\n"
        row.append(InlineKeyboardButton(text=f"🗑 {i}", callback_data=f"pl_rem_track|{name}|{i-1}"))
        
        # Max 5 buttons per row
        if len(row) == 5:
            buttons.append(row)
            row = []
            
    if row: 
        buttons.append(row)
        
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data=f"pl_view|{name}")])
    
    await CallbackQuery.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"^pl_rem_track\|") & ~BANNED_USERS)
async def pl_rem_track_cb(client, CallbackQuery):
    if CallbackQuery.message.chat.type != ChatType.PRIVATE:
        return await CallbackQuery.answer("⚠️ You can only remove tracks in my Private Chat!", show_alert=True)
    
    data = CallbackQuery.data.split("|")
    name = data[1]
    index = int(data[2])
    
    success = await remove_track_by_index(CallbackQuery.from_user.id, name, index)
    if success:
        await CallbackQuery.answer("✅ Track removed.", show_alert=True)
    else:
        await CallbackQuery.answer("❌ Track not found or already removed.", show_alert=True)
        
    # Refresh the edit view to show updated numbers
    await pl_edit_cb(client, CallbackQuery)

@app.on_callback_query(filters.regex(r"^pl_del\|") & ~BANNED_USERS)
async def pl_del_cb(client, CallbackQuery):
    if CallbackQuery.message.chat.type != ChatType.PRIVATE:
        return await CallbackQuery.answer(
            "⚠️ You can only delete folders in my Private Chat!", 
            show_alert=True, 
            url=f"https://t.me/{app.username}?start=playlist"
        )
    
    name = CallbackQuery.data.split("|")[1]
    success = await delete_user_playlist(CallbackQuery.from_user.id, name)
    
    if success:
        await CallbackQuery.answer(f"🗑 Deleted folder: {name}", show_alert=True)
    else:
        await CallbackQuery.answer("❌ Failed to delete folder.", show_alert=True)
        
    await pl_home_cb(client, CallbackQuery)
