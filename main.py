import os
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
from aiohttp import web
import db

# --- НАСТРОЙКИ БОТА ---
BOT_TOKEN = "8827288716:AAFFSfzwcjqTe5T8dFfILUr_gBRZTFTHMO0"
ADMIN_ID = 963471548  
JUDGE_STICKER_ID = "CAACAgIAAxkBAAFLhqRqIb-4vLS3FVbLJ6k_L0p5hIaJEAACLl0AAjT40Uostywl6JydUjsE" 

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
    waiting_for_lang = State() 

# --- СЛОВАРЬ ЯЗЫКОВ ---
TEXTS = {
    'ru': {
        'lang_select': '🌍 Пожалуйста, выберите язык бота:\n\nIltimos, bot tilini tanlang:',
        'welcome': '👑 <b>Добро пожаловать в Zenith Esports!</b>\n\nТвоя точка входа в мир киберспорта. Регистрируй команду на турниры серии Zenith Open, следи за расписанием матчей и получай мгновенную поддержку судей.\n\nВыбери нужное действие ниже 👇',
        'btn_reg': '🎮 Зарегистрировать команду',
        'btn_judge': '⚖️ Вызвать судью',
        'btn_rules': '📜 Правила турнира',
        'btn_settings': '⚙️ Настройки',
        'judge_text': '⚖️ <b>Вызов судьи / Обратная связь</b>\n\nОпишите вашу проблему, жалобу или оставьте комментарий. Сообщение будет передано напрямую администрации турнира.',
        'btn_cancel': '❌ Отменить',
        'cancel_msg': '❌ Вызов судьи отменен.',
        'success_complaint': '✅ Ваша жалоба успешно отправлена судьям. Ожидайте ответа.',
        'error_complaint': '❌ Произошла ошибка при отправке.',
        'player_reply': '💬 <b>Ответ от судьи Zenith:</b>\n\n{text}',
        'dialog_open_player': '🟢 <b>Судья присоединился к диалогу.</b>\n\nТеперь вы можете свободно общаться.',
        'dialog_close_player': '✅ Диалог с судьей завершен. Спасибо за обращение!',
        'msg_from_player': '📝 Сообщение от игрока (Диалог):\n\n{text}',
        'reply_from_admin': '💬 Ответ судьи:\n\n{text}',
    },
    'uz': {
        'lang_select': '🌍 Iltimos, bot tilini tanlang:\n\nПожалуйста, выберите язык бота:',
        'welcome': '👑 <b>Zenith Esports ga xush kelibsiz!</b>\n\nE-sport dunyosiga kirish eshigingiz. Zenith Open turnirlarida jamoangizni ro\'yxatdan o\'tkazing, o\'yinlar jadvalini kuzating va hakamlardan tezkor yordam oling.\n\nQuyidagi harakatlardan birini tanlang 👇',
        'btn_reg': "🎮 Jamoani ro'yxatdan o'tkazish",
        'btn_judge': '⚖️ Hakam chaqirish',
        'btn_rules': '📜 Turnir qoidalari',
        'btn_settings': '⚙️ Sozlamalar',
        'judge_text': "⚖️ <b>Hakam chaqirish / Fikr-mulohaza</b>\n\nMuammoningiz, shikoyatingiz yoki izohingizni yozing. Xabar bevosita turnir ma'muriyatiga yuboriladi.",
        'btn_cancel': '❌ Bekor qilish',
        'cancel_msg': "❌ Hakam chaqirish bekor qilindi.",
        'success_complaint': "✅ Shikoyatingiz hakamlarga muvaffaqiyatli yuborildi. Javobni kuting.",
        'error_complaint': '❌ Yuborishda xato yuz berdi.',
        'player_reply': '💬 <b>Zenith hakamidan javob:</b>\n\n{text}',
        "dialog_open_player": "🟢 <b>Hakam dialogga qo'shildi.</b>\n\nEndi erkin suhbat qurishingiz mumkin.",
        'dialog_close_player': "✅ Hakam bilan dialog yakunlandi. Murojaatingiz uchun rahmat!",
        'msg_from_player': '📝 O\'yinchidan xabar (Dialog):\n\n{text}',
        'reply_from_admin': '💬 Hakamdan javob:\n\n{text}',
    }
}

# --- ФУНКЦИИ ГЕНЕРАЦИИ КЛАВИАТУР ---
def get_lang_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru"),
         InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="set_lang_uz")]
    ])

def get_main_menu_kb(lang: str):
    t = TEXTS.get(lang, TEXTS['ru'])
    
    # Определяем ссылку на правила в зависимости от языка
    if lang == 'uz':
        rules_url = "https://telegra.ph/ZENITH-ESPORTS-REGLAMENTI-06-05"
    else:
        rules_url = "https://telegra.ph/REGLAMENT-ZENITH-ESPORTS-06-04"

    # Формируем новую структуру кнопок
    return InlineKeyboardMarkup(inline_keyboard=[
        # 1 ряд: Зеленая кнопка регистрации (type="primary" делает ее зеленой)
        [InlineKeyboardButton(
            text=t['btn_reg'], 
            web_app=WebAppInfo(url="https://benevolent-sawine-07ad42.netlify.app/", type="primary")
        )],
        
        # 2 ряд: Две кнопки рядом
        [
            InlineKeyboardButton(text=t['btn_judge'], callback_data="btn_judge"),
            InlineKeyboardButton(text=t['btn_rules'], url=rules_url)
        ],
        
        # 3 ряд: Настройки
        [InlineKeyboardButton(text=t['btn_settings'], callback_data="open_settings")]
    ])

# --- ФИЛЬТР ДИАЛОГА ---
def is_in_active_dialog(message: Message) -> bool:
    return message.from_user.id in active_dialogs

# --- 1. СТАРТ И ВЫБОР ЯЗЫКА ---
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    lang = db.get_user_lang(user_id)
    
    if lang:
        await message.answer(TEXTS[lang]['welcome'], reply_markup=get_main_menu_kb(lang))
    else:
        await message.answer(TEXTS['ru']['lang_select'], reply_markup=get_lang_kb())
        await state.set_state(JudgeStates.waiting_for_lang)

@router.callback_query(JudgeStates.waiting_for_lang, F.data.startswith("set_lang_"))
async def process_set_lang(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[-1] 
    db.set_user_lang(callback.from_user.id, lang)
    await state.clear()
    
    await callback.message.edit_text(
        TEXTS[lang]['welcome'], 
        reply_markup=get_main_menu_kb(lang)
    )
    await callback.answer()

# --- 2. НАСТРОЙКИ ---
@router.callback_query(F.data == "open_settings")
async def open_settings(callback: CallbackQuery):
    await callback.message.edit_text(
        TEXTS['ru']['lang_select'], 
        reply_markup=get_lang_kb()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("set_lang_"))
async def change_lang(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = callback.data.split("_")[-1]
    db.set_user_lang(callback.from_user.id, lang)
    
    await callback.message.edit_text(
        TEXTS[lang]['welcome'], 
        reply_markup=get_main_menu_kb(lang)
    )
    await callback.answer("✅ Настройки сохранены / Sozlamalar saqlandi", show_alert=False)

# --- 3. ВЫЗОВ СУДЬИ ---
@router.callback_query(F.data == "btn_judge")
async def process_judge(callback: CallbackQuery, state: FSMContext):
    lang = db.get_user_lang(callback.from_user.id) or 'ru'
    t = TEXTS[lang]
    
    sticker_msg = await callback.message.answer_sticker(JUDGE_STICKER_ID)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['btn_cancel'], callback_data="cancel_judge")]
    ])
    text_msg = await callback.message.answer(t['judge_text'], reply_markup=kb)
    
    await state.update_data(sticker_msg_id=sticker_msg.message_id, text_msg_id=text_msg.message_id, lang=lang)
    await state.set_state(JudgeStates.waiting_for_complaint)
    await callback.answer()

@router.callback_query(F.data == "cancel_judge", JudgeStates.waiting_for_complaint)
async def cancel_judge(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    chat_id = callback.message.chat.id
    lang = data.get('lang', 'ru')
    
    try: await bot.delete_message(chat_id=chat_id, message_id=data['sticker_msg_id'])
    except: pass
    try: await bot.delete_message(chat_id=chat_id, message_id=data['text_msg_id'])
    except: pass
        
    await state.clear()
    await callback.message.answer(TEXTS[lang]['cancel_msg'])
    await callback.answer()

@router.message(JudgeStates.waiting_for_complaint)
async def receive_complaint(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    t = TEXTS[lang]
    
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
        await message.answer(t['success_complaint'], reply_markup=get_main_menu_kb(lang))
    except:
        await message.answer(t['error_complaint'], reply_markup=get_main_menu_kb(lang))
    await state.clear()

# --- 4. ПАНЕЛЬ АДМИНА ---
@router.callback_query(F.data.startswith("reply_"))
async def admin_reply_request(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return await callback.answer("❌ Не для вас!", show_alert=True)
    user_id = int(callback.data.split("_")[1])
    await state.update_data(target_user_id=user_id)
    await callback.message.reply("💬 Напишите текст ответа (одноразово):")
    await state.set_state(JudgeStates.waiting_for_admin_reply)
    await callback.answer()

@router.message(JudgeStates.waiting_for_admin_reply, F.from_user.id == ADMIN_ID)
async def admin_send_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('target_user_id')
    lang = db.get_user_lang(user_id) or 'ru'
    
    try:
        await bot.send_message(user_id, TEXTS[lang]['player_reply'].format(text=message.text))
        await message.reply("✅ Ответ отправлен.")
    except:
        await message.reply("❌ Не удалось отправить.")
    await state.clear()

@router.callback_query(F.data.startswith("opendialog_"))
async def open_dialog(callback: CallbackQuery, state: FSMContext):
    global admin_current_target
    if callback.from_user.id != ADMIN_ID: return await callback.answer("❌ Не для вас!", show_alert=True)
    
    user_id = int(callback.data.split("_")[1])
    active_dialogs.add(user_id)
    admin_current_target = user_id
    
    await callback.message.edit_reply_markup(reply_markup=None)
    dialog_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Завершить диалог", callback_data=f"closedialog_{user_id}")]
    ])
    await callback.message.reply("🟢 <b>Диалог с игроком открыт.</b>\n\nВсе его сообщения будут приходить сюда. Просто пишите в этот чат.", reply_markup=dialog_kb)
    
    lang = db.get_user_lang(user_id) or 'ru'
    try:
        await bot.send_message(user_id, TEXTS[lang]['dialog_open_player'])
    except: pass
    await callback.answer()

@router.callback_query(F.data.startswith("closedialog_"))
async def close_dialog(callback: CallbackQuery):
    global admin_current_target
    if callback.from_user.id != ADMIN_ID: return await callback.answer("❌ Не для вас!", show_alert=True)
    
    user_id = int(callback.data.split("_")[1])
    active_dialogs.discard(user_id)
    if admin_current_target == user_id:
        admin_current_target = None
        
    await callback.message.edit_text("🛑 <b>Диалог с игроком завершен.</b>")
    
    lang = db.get_user_lang(user_id) or 'ru'
    try:
        await bot.send_message(user_id, TEXTS[lang]['dialog_close_player'])
    except: pass
    await callback.answer()

@router.callback_query(F.data.startswith("checked_"))
async def admin_checked(callback: CallbackQuery):
    global admin_current_target
    if callback.from_user.id != ADMIN_ID: return await callback.answer("❌ Не для вас!", show_alert=True)
    
    user_id = int(callback.data.split("_")[1])
    
    if user_id in active_dialogs:
        active_dialogs.discard(user_id)
        if admin_current_target == user_id:
            admin_current_target = None
        lang = db.get_user_lang(user_id) or 'ru'
        try:
            await bot.send_message(user_id, TEXTS[lang]['dialog_close_player'])
        except: pass

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply("✅ Жалоба отмечена как проверенная.")
    await callback.answer()

# --- 5. ПЕРЕХВАТ СООБЩЕНИЙ ---
@router.message(is_in_active_dialog, F.chat.type == "private")
async def player_dialog_message(message: Message):
    lang = db.get_user_lang(message.from_user.id) or 'ru'
    t = TEXTS[lang]
    await message.copy_to(chat_id=ADMIN_ID, caption=t['msg_from_player'].format(text=message.caption or message.text or ''))

@router.message(F.from_user.id == ADMIN_ID, F.chat.type == "private")
async def admin_dialog_message(message: Message):
    global admin_current_target
    if admin_current_target is not None and admin_current_target in active_dialogs:
        lang = db.get_user_lang(admin_current_target) or 'ru'
        t = TEXTS[lang]
        await message.copy_to(chat_id=admin_current_target, caption=t['reply_from_admin'].format(text=message.caption or message.text or ''))

# --- 6. МОНИТОРИНГ ГРУППЫ ---
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
async def web_server_handler(request):
    return web.Response(text="OK", status=200)

async def main():
    db.init_db()
    print("Бот Zenith Esports запущен!")
    await bot.delete_webhook(drop_pending_updates=True)

    app = web.Application()
    app.router.add_get('/', web_server_handler)
    port = int(os.environ.get("PORT", 8000))
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Фоновый веб-сервер запущен на порту {port}")

    await asyncio.gather(
        dp.start_polling(bot),
        asyncio.Event().wait()
    )

if __name__ == "__main__":
    asyncio.run(main())