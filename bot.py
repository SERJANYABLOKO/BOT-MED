import os
import logging
import random
import asyncio
from telegram import Update, ChatMember
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ChatMemberHandler
from aiohttp import web
import group_utils

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN_BOT = os.environ.get("TOKEN_BOT")
PORT = int(os.environ.get("PORT", 8080))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# Хранилище фото для групп (group_id: list of file_ids)
group_photos = {}

# ======================
# Обработчики команд
# ======================

async def start_command(update: Update, context: CallbackContext):
    """Приветствие при добавлении бота в группу"""
    chat = update.effective_chat
    
    if chat.type == "private":
        await update.message.reply_text(
            "👋 Привет! Добавь меня в группу, и я буду доступен там.\n\n"
            "📌 Команды в группе:\n"
            "/photo - отправить случайное фото из этой группы\n"
            "/sex - выбрать двух случайных участников"
        )
    else:
        await update.message.reply_text(
            "👋 Привет! Я бот для этой группы.\n\n"
            "📌 Доступные команды:\n"
            "/photo - отправить случайное фото из этой группы\n"
            "/sex - выбрать двух случайных участников"
        )

async def collect_existing_photos(update: Update, context: CallbackContext):
    """Собирает все фото из группы при добавлении бота или по команде"""
    chat_id = update.effective_chat.id
    
    # Создаём задачу на сбор фото в фоне
    context.application.create_task(
        group_utils.collect_all_group_photos(context.bot, chat_id, group_photos)
    )
    
    await update.message.reply_text(
        "📸 Начинаю сбор фото из этой группы...\n"
        "Это может занять некоторое время в зависимости от количества сообщений.\n"
        "После завершения сбора команда /photo будет работать."
    )

async def photo_command(update: Update, context: CallbackContext):
    """Отправляет случайное фото из группы"""
    chat_id = update.effective_chat.id
    
    if chat_id not in group_photos or not group_photos[chat_id]:
        await update.message.reply_text(
            "📸 В этой группе пока нет сохранённых фото.\n"
            "Убедитесь, что бот был добавлен в группу и отправьте команду /collect_photos для сбора фото из истории."
        )
        return
    
    random_photo = random.choice(group_photos[chat_id])
    
    try:
        await update.message.reply_photo(random_photo)
        logger.info(f"📸 Отправлено случайное фото в чат {chat_id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке фото: {e}")
        await update.message.reply_text("❌ Не удалось отправить фото.")

async def collect_photos_command(update: Update, context: CallbackContext):
    """Команда для ручного сбора фото из группы"""
    chat_id = update.effective_chat.id
    
    await update.message.reply_text(
        "📸 Начинаю сбор фото из этой группы...\n"
        "Это может занять некоторое время."
    )
    
    await group_utils.collect_all_group_photos(context.bot, chat_id, group_photos)
    
    photo_count = len(group_photos.get(chat_id, []))
    await update.message.reply_text(
        f"✅ Сбор завершён! Найдено {photo_count} фото.\n"
        f"Теперь можно использовать команду /photo для отправки случайного фото."
    )

async def sex_command(update: Update, context: CallbackContext):
    """Выбирает двух случайных участников группы и пишет '1 выебал 2'"""
    chat_id = update.effective_chat.id
    
    # Получаем список участников чата
    members = await group_utils.get_chat_members(context.bot, chat_id)
    
    if len(members) < 2:
        await update.message.reply_text(
            "👥 В этой группе меньше 2 участников, чтобы выбрать двоих."
        )
        return
    
    # Выбираем двух случайных участников
    selected = random.sample(members, 2)
    user1 = selected[0]
    user2 = selected[1]
    
    # Формируем имена
    name1 = group_utils.get_user_display_name(user1)
    name2 = group_utils.get_user_display_name(user2)
    
    # Если это бот, пробуем выбрать другого
    if user1.id == context.bot.id or user2.id == context.bot.id:
        # Фильтруем бота из списка
        non_bot_members = [m for m in members if m.id != context.bot.id]
        if len(non_bot_members) >= 2:
            selected = random.sample(non_bot_members, 2)
            user1, user2 = selected[0], selected[1]
            name1 = group_utils.get_user_display_name(user1)
            name2 = group_utils.get_user_display_name(user2)
        elif len(non_bot_members) == 1:
            await update.message.reply_text(
                f"👥 {group_utils.get_user_display_name(non_bot_members[0])} не может выебать сам себя! Добавьте в группу больше людей."
            )
            return
        else:
            await update.message.reply_text("👥 В группе нет других участников, кроме бота.")
            return
    
    message = f"🔥 {name1} выебал {name2}"
    await update.message.reply_text(message)
    logger.info(f"🔥 {message} в чате {chat_id}")

async def handle_new_photo(update: Update, context: CallbackContext):
    """Сохраняет новые фото, отправленные в группу"""
    chat_id = update.effective_chat.id
    
    # Только для групп
    if update.effective_chat.type not in ["group", "supergroup"]:
        return
    
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        
        if chat_id not in group_photos:
            group_photos[chat_id] = []
        
        if file_id not in group_photos[chat_id]:
            group_photos[chat_id].append(file_id)
            logger.info(f"📸 Сохранено новое фото в чате {chat_id}")

# ИСПРАВЛЕННЫЙ ОБРАБОТЧИК СТАТУСА
async def status_handler(update: Update, context: CallbackContext):
    """Обрабатывает добавление бота в группу"""
    # Проверяем наличие my_chat_member в update
    if not update.my_chat_member:
        return
    
    status = update.my_chat_member.new_chat_member.status
    chat_id = update.my_chat_member.chat.id
    
    # Проверяем, был ли бот добавлен в группу
    if status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR]:
        logger.info(f"✅ Бот добавлен в группу {chat_id}")
        # Отправляем приветственное сообщение в группу
        await context.bot.send_message(
            chat_id=chat_id,
            text="👋 Привет! Я бот для этой группы.\n\n"
                 "📌 Доступные команды:\n"
                 "/photo - отправить случайное фото из этой группы\n"
                 "/sex - выбрать двух случайных участников\n"
                 "/collect_photos - собрать все фото из истории группы\n\n"
                 "📸 Для работы /photo необходимо сначала собрать фото командой /collect_photos"
        )

# ======================
# Создание приложения
# ======================

def setup_application():
    app = Application.builder().token(TOKEN_BOT).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("photo", photo_command))
    app.add_handler(CommandHandler("sex", sex_command))
    app.add_handler(CommandHandler("collect_photos", collect_photos_command))
    
    # Обработчики
    app.add_handler(MessageHandler(filters.PHOTO, handle_new_photo))
    # ИСПРАВЛЕНО: используем ChatMemberHandler вместо MessageHandler
    app.add_handler(ChatMemberHandler(status_handler, ChatMemberHandler.CHAT_MEMBER))
    
    return app

# ======================
# Webhook обработчики для aiohttp
# ======================

async def webhook_handler(request):
    """Обработчик вебхуков от Telegram"""
    try:
        data = await request.json()
        bot_app = request.app['bot_app']
        update = Update.de_json(data, bot_app.bot)
        await bot_app.process_update(update)
        logger.info("✅ Webhook обработан")
        return web.Response(text="OK", status=200)
    except Exception as e:
        logger.error(f"❌ Ошибка в webhook: {e}")
        return web.Response(text="Error", status=500)

async def health_handler(request):
    """Health check handler"""
    return web.Response(text="OK", status=200)

async def main():
    """Главная функция"""
    logger.info("🚀 Запуск бота для групп...")
    
    if not TOKEN_BOT:
        logger.error("❌ TOKEN_BOT не задан в переменных окружения")
        return
    
    ptb_app = setup_application()
    await ptb_app.initialize()
    
    if WEBHOOK_URL:
        logger.info(f"🌐 Режим вебхука на порту {PORT}")
        webhook_url = f"{WEBHOOK_URL}/webhook"
        result = await ptb_app.bot.set_webhook(url=webhook_url, drop_pending_updates=True)
        
        if result:
            logger.info(f"✅ Вебхук успешно установлен: {webhook_url}")
        else:
            logger.error("❌ Не удалось установить вебхук")
            return
        
        app = web.Application()
        app['bot_app'] = ptb_app
        app.router.add_post('/webhook', webhook_handler)
        app.router.add_get('/health', health_handler)
        app.router.add_get('/', health_handler)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', PORT)
        await site.start()
        
        logger.info(f"✅ Бот запущен на порту {PORT}")
        await asyncio.Event().wait()
        
    else:
        logger.warning("⚠️ WEBHOOK_URL не указан, используем polling")
        await ptb_app.start()
        await ptb_app.updater.start_polling()
        logger.info("✅ Бот запущен в режиме polling")
        
        while True:
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
