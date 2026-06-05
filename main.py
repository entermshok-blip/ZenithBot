import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, WebAppInfo
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import db

# --- НАСТРОЙКИ БОТА ---
BOT_TOKEN = "8827288716:AAFFSfzwcjqTe5T8dFfILUr_gBRZTFTHMO0"
ADMIN_ID = 963471548  # ВПИШИ СВОЙ TELEGRAM ID
JUDGE_STICKER_ID = "CAACAgIAAxkBAAFLhqRqIb-4vLS3FVbLJ6k_L0p5hIaJEAACLl0AAjT40Uostywl6JydUjsE" # ВПИШИ ID СТИКЕРА СУДЬИ

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# --- ХРАНИЛИЩЕ ДИАЛОГОВ ---
active_dialogs = set() 
admin_current_target = None 

# --- СОСТОЯНИЯ ---
class JudgeStates(StatesGroup):
    waiting_for_complaint = State()
    waiting_for_admin_reply = State()

# --- НАДЕЖНЫЙ ФИЛЬТР ДЛЯ ДИАЛОГА ---
def is_in_active_dialog(message: Message) -> bool:
    return message.from_user.id in active_dialogs

# --- КЛАВИАТУРЫ ---
def get_main_menu_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Зарегистрировать команду", web_app=WebAppInfo(url="https://benevolent-sawine-07ad42.netlify.app/"))],
        [InlineKeyboardButton(text="⚖️ Вызвать судью", callback_data="btn_judge")],
        [InlineKeyboardButton(text="📜 Правила турнира", url="https://telegra.ph/REGLAMENT-ZENITH-ESPORTS-06-04")]
    ])
    return kb

# --- 1. ПРИВЕТСТВИЕ ---
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    caption_text = (
        "👑 <b>Добро пожаловать в Zenith Esports!</b>\n\n"
        "Твоя точка входа в мир киберспорта. Регистрируй команду на турниры серии Zenith Open, "
        "следи за расписанием матчей и получай мгновенную поддержку судей.\n\n"
        "Выбери нужное действие ниже 👇"
    )
    await message.answer(caption_text, reply_markup=get_main_menu_kb())

# --- 2. ВЫЗОВ СУДЬИ ---
@router.callback_query(F.data == "btn_judge")
async def process_judge(callback: CallbackQuery, state: FSMContext):
    sticker_msg = await callback.message.answer_sticker(JUDGE_STICKER_ID)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_judge")]
    ])
    text = "⚖️ <b>Вызов судьи / Обратная связь</b>\n\nОпишите вашу проблему, жалобу или оставьте комментарий. Сообщение будет передано напрямую администрации турнира."
    text_msg = await callback.message.answer(text, reply_markup=kb)
    await state.update_data(sticker_msg_id=sticker_msg.message_id, text_msg_id=text_msg.message_id)
    await state.set_state(JudgeStates.waiting_for_complaint)
    await callback.answer()

@router.callback_query(F.data == "cancel_judge", JudgeStates.waiting_for_complaint)
async def cancel_judge(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    chat_id = callback.message.chat.id
    try: await bot.delete_message(chat_id=chat_id, message_id=data['sticker_msg_id'])
    except: pass
    try: await bot.delete_message(chat_id=chat_id, message_id=data['text_msg_id'])
    except: pass
    await state.clear()
    await callback.message.answer("❌ Вызов судьи отменен.")
    await callback.answer()

# Принимаем первую жалобу
@router.message(JudgeStates.waiting_for_complaint)
async def receive_complaint(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Без юзернейма"
    complaint_text = message.text

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Ответить игроку", callback_data=f"reply_{user_id}")],
        [InlineKeyboardButton(text="🟢 Открыть диалог", callback_data=f"opendialog_{user_id}")],
        [InlineKeyboardButton(text="✅ Проверка", callback_data=f"checked_{user_id}")]
    ])

    admin_text = (
        f"⚖️ <b>Новая жалоба</b>\n"
        f"👤 От: @{username} (ID: <code>{user_id}</code>)\n\n"
        f"📝 Текст:\n{complaint_text}"
    )

    try:
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_kb)
        await message.answer("✅ Ваша жалоба успешно отправлена судьям. Ожидайте ответа.", reply_markup=get_main_menu_kb())
    except:
        await message.answer("❌ Произошла ошибка при отправке.", reply_markup=get_main_menu_kb())
    await state.clear()

# --- 3. ДЕЙСТВИЯ АДМИНА С КНОПКАМИ ---

@router.callback_query(F.data.startswith("reply_"))
async def admin_reply_request(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return await callback.answer("❌ Не для вас!", show_alert=True)
    user_id = int(callback.data.split("_")[1])
    await state.update_data(target_user_id=user_id)
    await callback.message.reply("💬 Напишите текст ответа (одноразово):")
    await state.set_state(JudgeStates.waiting_for_admin_reply)
    await callback.answer()

@router.callback_query(F.data.startswith("opendialog_"))
async def open_dialog(callback: CallbackQuery, state: FSMContext):
    global admin_current_target
    if callback.from_user.id != ADMIN_ID: return await callback.answer("❌ Не для вас!", show_alert=True)
    
    user_id = int(callback.data.split("_")[1])
    active_dialogs.add(user_id)
    admin_current_target = user_id
    
    # Убираем старые кнопки у сообщения с жалобой
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # НОВАЯ КЛАВИАТУРА ДЛЯ ДИАЛОГА
    dialog_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Завершить диалог", callback_data=f"closedialog_{user_id}")]
    ])
    
    # Отправляем красивое сообщение с кнопкой завершения
    await callback.message.reply(
        "🟢 <b>Диалог с игроком открыт.</b>\n\nВсе его сообщения будут приходить сюда. Просто пишите в этот чат.", 
        reply_markup=dialog_kb
    )
    
    try:
        await bot.send_message(user_id, "🟢 <b>Судья присоединился к диалогу.</b>\n\nТеперь вы можете свободно общаться.")
    except: pass
    await callback.answer()

# НОВАЯ КНОПКА: Завершить диалог
@router.callback_query(F.data.startswith("closedialog_"))
async def close_dialog(callback: CallbackQuery):
    global admin_current_target
    if callback.from_user.id != ADMIN_ID: return await callback.answer("❌ Не для вас!", show_alert=True)
    
    user_id = int(callback.data.split("_")[1])
    
    # Выходим из диалога
    active_dialogs.discard(user_id)
    if admin_current_target == user_id:
        admin_current_target = None
        
    # Меняем текст сообщения и убираем кнопку
    await callback.message.edit_text("🛑 <b>Диалог с игроком завершен.</b>")
    
    # Уведомляем игрока
    try:
        await bot.send_message(user_id, "✅ Диалог с судьей завершен. Спасибо за обращение!")
    except: pass
    await callback.answer()

@router.callback_query(F.data.startswith("checked_"))
async def admin_checked(callback: CallbackQuery):
    global admin_current_target
    if callback.from_user.id != ADMIN_ID: return await callback.answer("❌ Не для вас!", show_alert=True)
    
    user_id = int(callback.data.split("_")[1])
    
    # На случай, если админ нажал "Проверка" не закрыв диалог
    if user_id in active_dialogs:
        active_dialogs.discard(user_id)
        if admin_current_target == user_id:
            admin_current_target = None
        try:
            await bot.send_message(user_id, "✅ Диалог с судьей завершен. Спасибо за обращение!")
        except: pass

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply("✅ Жалоба отмечена как проверенная.")
    await callback.answer()

# --- 4. ПЕРЕХВАТ СООБЩЕНИЙ ---

@router.message(JudgeStates.waiting_for_admin_reply, F.from_user.id == ADMIN_ID)
async def admin_send_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('target_user_id')
    try:
        await bot.send_message(user_id, f"💬 <b>Ответ от судьи Zenith:</b>\n\n{message.text}")
        await message.reply("✅ Ответ отправлен.")
    except:
        await message.reply("❌ Не удалось отправить.")
    await state.clear()

# Сообщения от Игрока -> Админу
@router.message(is_in_active_dialog, F.chat.type == "private")
async def player_dialog_message(message: Message):
    await message.copy_to(chat_id=ADMIN_ID, caption=f"📝 Сообщение от игрока (Диалог):\n\n{message.caption or message.text or ''}")

# Сообщения от Админа -> Игроку
@router.message(F.from_user.id == ADMIN_ID, F.chat.type == "private")
async def admin_dialog_message(message: Message):
    global admin_current_target
    if admin_current_target is not None and admin_current_target in active_dialogs:
        await message.copy_to(chat_id=admin_current_target, caption=f"💬 Ответ судьи:\n\n{message.caption or message.text or ''}")

# --- 5. МОНИТОРИНГ ГРУППЫ ---
@router.message(F.chat.type.in_({"group", "supergroup"}), ~F.from_user.is_bot)
async def group_monitor(message: Message):
    text = message.text or message.caption or ""
    hashtags = [word for word in text.split() if word.startswith("#")]
    
    if hashtags:
        group_name = message.chat.title or "Неизвестная группа"
        sender = message.from_user.username or message.from_user.first_name or "Аноним"
        
        admin_text = (
            f"📥 <b>Данные из группы</b> [{group_name}]\n"
            f"👤 Отправил: @{sender}\n"
            f"🏷 Теги: {', '.join(hashtags)}\n\n"
        )
        
        clean_text = text.replace("#results", "").replace("#result", "").strip()
        if clean_text:
            admin_text += f"💬 Текст: {clean_text}"
        else:
            admin_text += "🖼 Скриншот/Медиафайл прикреплен ниже."

        await bot.send_message(ADMIN_ID, admin_text)
        
        if message.photo:
            await bot.send_photo(ADMIN_ID, photo=message.photo[-1].file_id)
        elif message.document:
            await bot.send_document(ADMIN_ID, document=message.document.file_id)

# --- ЗАПУСК ---
async def main():
    db.init_db()
    print("Бот Zenith Esports запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())