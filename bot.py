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
# ======================
# НОВЫЕ КОМАНДЫ
# ======================

async def drink_command(update: Update, context: CallbackContext):
    """Выбирает, кто сегодня заказывает алкоголь"""
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return
    
    members = await group_utils.get_chat_members(context.bot, chat_id, update)
    
    if not members:
        await update.message.reply_text("👥 Не удалось найти участников в группе.")
        return
    
    # Фильтруем бота
    non_bot_members = [m for m in members if m.id != context.bot.id]
    if not non_bot_members:
        await update.message.reply_text("🤖 В группе нет людей, кроме бота!")
        return
    
    chosen = random.choice(non_bot_members)
    name = group_utils.get_user_display_name(chosen)
    
    actions = [
        f"🍺 Сегодня алкоголь заказывает {name}! Готовь кошелёк! 💸",
        f"🥃 {name}, твоя очередь раскошелиться на выпивку! 🍻",
        f"🍾 Бармен! {name} сегодня платит за всё! 🎉",
        f"💳 {name}, доставай карту - сегодня ты спонсор вечеринки! 🥂"
    ]
    
    message = random.choice(actions)
    await update.message.reply_text(message)
    logger.info(f"🍺 Выбран покупатель алкоголя: {name} в чате {chat_id}")

async def real_command(update: Update, context: CallbackContext):
    """Показывает ближайшие 3 матча Real Madrid (автообновление через API-Football)"""
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return
    
    # Отправляем сообщение о загрузке
    loading_msg = await update.message.reply_text("⚽ Загружаю расписание матчей Real Madrid...")
    
    # ID команды Real Madrid в API-Football (541)
    REAL_MADRID_ID = 541
    
    if not API_FOOTBALL_KEY:
        await loading_msg.edit_text(
            "⚠️ API ключ не настроен.\n\n"
            "Добавьте переменную окружения API_FOOTBALL_KEY в настройках Render.\n"
            "Получить бесплатный ключ: dashboard.api-football.com/register"
        )
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            # Формируем запрос к API-Football
            url = "https://v3.football.api-sports.io/fixtures"
            headers = {
                "x-apisports-key": API_FOOTBALL_KEY
            }
            params = {
                "team": REAL_MADRID_ID,
                "next": 3,  # Следующие 3 матча
                "season": "2025"  # Текущий сезон
            }
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    fixtures = data.get("response", [])
                    
                    if not fixtures:
                        await loading_msg.edit_text(
                            "❌ Не удалось найти ближайшие матчи.\n"
                            "Возможно, сезон закончился или данные ещё не обновились."
                        )
                        return
                    
                    # Формируем красивое сообщение
                    message = "⚽ **БЛИЖАЙШИЕ МАТЧИ REAL MADRID** ⚽\n\n"
                    message += f"📅 *Данные на {datetime.now().strftime('%d.%m.%Y %H:%M')}*\n"
                    message += f"🆔 *API-Football (бесплатно)*\n\n"
                    
                    for i, fixture in enumerate(fixtures, 1):
                        match_date = datetime.fromisoformat(fixture['fixture']['date'].replace('Z', '+00:00'))
                        
                        # Определяем, где играет Реал
                        home_team = fixture['teams']['home']['name']
                        away_team = fixture['teams']['away']['name']
                        is_home = (home_team == "Real Madrid")
                        opponent = away_team if is_home else home_team
                        
                        # Стадион
                        venue = fixture['fixture']['venue']['name']
                        
                        # Турнир
                        league = fixture['league']['name']
                        league_icon = {
                            "La Liga": "🇪🇸",
                            "UEFA Champions League": "🏆",
                            "Copa del Rey": "👑",
                            "Supercopa de España": "🇪🇸"
                        }.get(league, "⚽")
                        
                        message += f"**{i}. {league_icon} {league}**\n"
                        message += f"🆚 Против: **{opponent}**\n"
                        message += f"📅 Дата: {match_date.strftime('%d %B %Y')}\n"
                        message += f"⏰ Время: {match_date.strftime('%H:%M')} UTC\n"
                        message += f"📍 Стадион: {venue}\n"
                        
                        # Добавляем статус, если матч уже начался
                        status = fixture['fixture']['status']['short']
                        if status == "1H" or status == "2H" or status == "HT":
                            message += f"🔥 **Матч В ИГРЕ!** 🔥\n"
                        elif status == "FT":
                            score_home = fixture['goals']['home']
                            score_away = fixture['goals']['away']
                            message += f"📊 **Счёт: {score_home} : {score_away}**\n"
                        
                        message += "\n" + "─" * 30 + "\n\n"
                    
                    message += "🏆 **Турнирное положение:**\n"
                    message += "• Реал Мадрид борется за титулы в Ла Лиге и ЛЧ\n\n"
                    message += "💪 **¡Hala Madrid!**"
                    
                    await loading_msg.edit_text(message, parse_mode='Markdown')
                    logger.info(f"⚽ Команда /real показала матчи в чате {chat_id}")
                    
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка API: {response.status} - {error_text}")
                    await loading_msg.edit_text(
                        "❌ Ошибка при получении данных с API-Football.\n\n"
                        f"Код ошибки: {response.status}\n\n"
                        "Возможные причины:\n"
                        "• Превышен лимит запросов (100/день на бесплатном тарифе)\n"
                        "• Неверный API ключ\n"
                        "• API временно недоступен"
                    )
                    
    except aiohttp.ClientError as e:
        logger.error(f"Ошибка сети при запросе к API-Football: {e}")
        await loading_msg.edit_text(
            "❌ Ошибка сети при получении данных.\n"
            "Пожалуйста, попробуйте позже."
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка в /real: {e}")
        await loading_msg.edit_text(
            "❌ Произошла неизвестная ошибка.\n"
            "Пожалуйста, попробуйте позже."
        )

async def porno_command(update: Update, context: CallbackContext):
    """Провокационная команда про Илью, Эдика, Аслана и Злату"""
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return
    
    # Список возможных сообщений
    actions = [
        "🔥 Илья, Эдик и Аслан выебали Злату втроём! 🍆💦",
        "😈 Злата получила свою порцию от Ильи, Эдика и Аслана! 👊🍑",
        "💥 Илья забил первый, Эдик продолжил, Аслан добил - Злата в шоке! 😱",
        "🥵 Злата не ожидала такого жёсткого трио от Ильи, Эдика и Аслана! 🍌🍌🍌",
        "😏 Илья, Эдик и Аслан устроили Злате ночь, которую она не забудет! 🔥",
        "💢 Злата кричала, пока Илья, Эдик и Аслан делали своё дело! 😫💦",
        "🍆🍆🍆 Илья, Эдик и Аслан показали Злате, что такое настоящий мужской подход! 💪",
        "🔥🛏️ Злата была разорвана в клочья Ильёй, Эдиком и Асланом! 💀",
        "😈 Сегодня Злата - главная звезда взрослого кино в компании Ильи, Эдика и Аслана! 🎬🔥",
        "💦 Трое против одной: Илья, Эдик и Аслан не оставили от Златы мокрого места! 🌊"
    ]
    
    # Выбираем случайное сообщение
    message = random.choice(actions)
    
    await update.message.reply_text(message)
    logger.info(f"🔞 Команда /porno использована в чате {chat_id}")

async def kiss_command(update: Update, context: CallbackContext):
    """Романтический поцелуй между двумя участниками"""
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return
    
    members = await group_utils.get_chat_members(context.bot, chat_id, update)
    
    if len(members) < 2:
        await update.message.reply_text("👥 В группе меньше 2 человек для поцелуя!")
        return
    
    # Выбираем двух разных участников
    selected = random.sample(members, 2)
    user1, user2 = selected[0], selected[1]
    
    name1 = group_utils.get_user_display_name(user1)
    name2 = group_utils.get_user_display_name(user2)
    
    actions = [
        f"💏 {name1} и {name2} страстно поцеловались! 😘",
        f"💋 {name1} чмокнул(а) {name2} в щёчку! 🥰",
        f"🔥 {name1} и {name2} - новая парочка в группе! 💕",
        f"😳 {name1} украл(а) поцелуй у {name2}! 💋"
    ]
    
    message = random.choice(actions)
    await update.message.reply_text(message)
    logger.info(f"💏 Поцелуй между {name1} и {name2} в чате {chat_id}")

async def fight_command(update: Update, context: CallbackContext):
    """Битва между двумя участниками"""
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return
    
    members = await group_utils.get_chat_members(context.bot, chat_id, update)
    
    if len(members) < 2:
        await update.message.reply_text("👥 Нужно минимум 2 бойца для битвы!")
        return
    
    # Выбираем двух бойцов
    fighters = random.sample(members, 2)
    fighter1, fighter2 = fighters[0], fighters[1]
    
    name1 = group_utils.get_user_display_name(fighter1)
    name2 = group_utils.get_user_display_name(fighter2)
    
    # Определяем победителя
    winner = random.choice([fighter1, fighter2])
    winner_name = group_utils.get_user_display_name(winner)
    
    actions = [
        f"🥊 БИТВА! {name1} VS {name2}\n\n💪 ПОБЕДИТЕЛЬ: {winner_name}! 🏆",
        f"⚔️ {name1} и {name2} сражаются не на жизнь, а на смерть!\n\n🎉 {winner_name} выходит победителем! 🎉",
        f"💥 {name1} наносит удар! {name2} контратакует!\n\n🏅 Побеждает {winner_name}! 🔥",
        f"👊 {name1} и {name2} устроили замес!\n\n✨ Чемпион сегодня - {winner_name}! ✨"
    ]
    
    message = random.choice(actions)
    await update.message.reply_text(message)
    logger.info(f"🥊 Битва между {name1} и {name2}, победил {winner_name} в чате {chat_id}")

async def marry_command(update: Update, context: CallbackContext):
    """Женит двух случайных участников"""
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return
    
    members = await group_utils.get_chat_members(context.bot, chat_id, update)
    
    if len(members) < 2:
        await update.message.reply_text("👥 Нужно минимум 2 человека для свадьбы!")
        return
    
    # Выбираем пару
    couple = random.sample(members, 2)
    spouse1, spouse2 = couple[0], couple[1]
    
    name1 = group_utils.get_user_display_name(spouse1)
    name2 = group_utils.get_user_display_name(spouse2)
    
    actions = [
        f"💍 {name1} и {name2} поженились! Поздравляем молодожёнов! 🎉🥂",
        f"👰‍♀️🤵‍♂️ Объявляем {name1} и {name2} мужем и женой! 💒",
        f"💕 {name1} сделал(а) предложение {name2}! Согласие получено! 💍",
        f"🎊 СВАДЬБА! {name1} + {name2} = любовь навеки! 💑"
    ]
    
    message = random.choice(actions)
    await update.message.reply_text(message)
    logger.info(f"💍 Свадьба между {name1} и {name2} в чате {chat_id}")
    
    # Сохраняем пару в контексте (опционально)
    if 'married_couples' not in context.bot_data:
        context.bot_data['married_couples'] = {}
    context.bot_data['married_couples'][f"{spouse1.id}_{spouse2.id}"] = True

async def roast_command(update: Update, context: CallbackContext):
    """Подкалывает случайного участника"""
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return
    
    members = await group_utils.get_chat_members(context.bot, chat_id, update)
    
    if not members:
        await update.message.reply_text("👥 Не удалось найти участников.")
        return
    
    # Фильтруем бота и текущего пользователя (опционально)
    available = [m for m in members if m.id != context.bot.id]
    if not available:
        available = members
    
    target = random.choice(available)
    name = group_utils.get_user_display_name(target)
    
    roasts = [
        f"🔥 {name}, ты такой медленный, что твои мысли застревают в пробках! 🚗",
        f"😅 {name}, если бы тупость была олимпийским видом спорта, ты бы взял золото! 🥇",
        f"🤣 {name}, твой аватар выглядит умнее, чем ты!",
        f"💀 {name}, ты единственный человек, который может потеряться в очереди из одного человека!",
        f"😂 {name}, у тебя лицо как у подержанного автомобиля - много пробега и куча проблем! 🚗",
        f"😆 {name}, твои шутки такие же острые, как мокрый носок! 🧦",
        f"🎯 {name}, ты - живое доказательство того, что эволюция может ошибаться! 🧬"
    ]
    
    message = random.choice(roasts)
    await update.message.reply_text(message)
    logger.info(f"🔥 Подкол участника {name} в чате {chat_id}")

async def whip_command(update: Update, context: CallbackContext):
    """Наказывает случайного участника"""
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return
    
    members = await group_utils.get_chat_members(context.bot, chat_id, update)
    
    if not members:
        await update.message.reply_text("👥 Не удалось найти участников.")
        return
    
    # Фильтруем бота
    available = [m for m in members if m.id != context.bot.id]
    if not available:
        available = members
    
    target = random.choice(available)
    name = group_utils.get_user_display_name(target)
    
    punishments = [
        f"🔨 {name} получает 10 ударов плетью! 👋",
        f"⚡ {name}, ты наказан! Теперь ты будешь мыть посуду неделю! 🧽",
        f"😈 {name}, твоё наказание - написать 100 раз 'Я больше не буду шалить'! 📝",
        f"💢 {name}, ты отправлен в угол на 30 минут! 🚫",
        f"🎭 {name}, твоё наказание - станцевать ламбаду перед всей группой! 💃"
    ]
    
    message = random.choice(punishments)
    await update.message.reply_text(message)
    logger.info(f"🔨 Наказание участника {name} в чате {chat_id}")

async def slap_command(update: Update, context: CallbackContext):
    """Один участник даёт пощёчину другому"""
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return
    
    members = await group_utils.get_chat_members(context.bot, chat_id, update)
    
    if len(members) < 2:
        await update.message.reply_text("👥 Нужно минимум 2 человека для пощёчины!")
        return
    
    # Выбираем агрессора и жертву
    slapper, victim = random.sample(members, 2)
    
    name1 = group_utils.get_user_display_name(slapper)
    name2 = group_utils.get_user_display_name(victim)
    
    actions = [
        f"👋 {name1} дал(а) пощёчину {name2}! Звук был слышен на весь район! 💥",
        f"🤚 {name1} отвесил(а) звонкую оплеуху {name2}! 😱",
        f"💨 {name1} - БАЦ! {name2} получил(а) по лицу! 👋",
        f"⚡ {name1} разозлился(ась) и влепил(а) {name2}! Берегитесь! 😡"
    ]
    
    message = random.choice(actions)
    await update.message.reply_text(message)
    logger.info(f"👋 Пощёчина от {name1} к {name2} в чате {chat_id}")

async def hug_command(update: Update, context: CallbackContext):
    """Обнимашки между участниками"""
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return
    
    members = await group_utils.get_chat_members(context.bot, chat_id, update)
    
    if len(members) < 2:
        await update.message.reply_text("👥 Нужен кто-то для обнимашек!")
        return
    
    # Можно выбрать конкретного или случайного
    if context.args:
        # Если указан username
        target_username = context.args[0].replace('@', '')
        target_user = None
        for m in members:
            if m.username == target_username:
                target_user = m
                break
        
        if target_user:
            hugger = update.effective_user
            name1 = group_utils.get_user_display_name(hugger)
            name2 = group_utils.get_user_display_name(target_user)
        else:
            # Если не найден, выбираем случайного
            hugger, target = random.sample(members, 2)
            name1 = group_utils.get_user_display_name(hugger)
            name2 = group_utils.get_user_display_name(target)
    else:
        # Случайные участники
        hugger, target = random.sample(members, 2)
        name1 = group_utils.get_user_display_name(hugger)
        name2 = group_utils.get_user_display_name(target)
    
    actions = [
        f"🤗 {name1} обнял(а) {name2}! Так тепло! 🥰",
        f"💕 {name1} и {name2} обнялись! Дружба победила! 🤝",
        f"🫂 {name1} дарит {name2} крепкие объятия! ❤️",
        f"😊 {name1} обнимает {name2} и желает хорошего дня! 🌟"
    ]
    
    message = random.choice(actions)
    await update.message.reply_text(message)
    logger.info(f"🤗 Обнимашки между {name1} и {name2} в чате {chat_id}")

async def betray_command(update: Update, context: CallbackContext):
    """Выбирает предателя в группе"""
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return
    
    members = await group_utils.get_chat_members(context.bot, chat_id, update)
    
    if not members:
        await update.message.reply_text("👥 Не удалось найти участников.")
        return
    
    # Фильтруем бота
    available = [m for m in members if m.id != context.bot.id]
    if not available:
        available = members
    
    traitor = random.choice(available)
    name = group_utils.get_user_display_name(traitor)
    
    betrayals = [
        f"🔪 {name} оказался предателем! Все против {name}! 😱",
        f"💀 Шокирующая новость! {name} продал группу врагам! 🕵️",
        f"⚠️ Внимание! {name} - двойной агент! Вычислили! 🎯",
        f"🏴‍☠️ {name} украл все печеньки из секретной комнаты! Позор! 🍪"
    ]
    
    message = random.choice(betrayals)
    await update.message.reply_text(message)
    logger.info(f"🔪 Предатель {name} обнаружен в чате {chat_id}")


async def start_command(update: Update, context: CallbackContext):
    """Приветствие при добавлении бота в группу"""
    chat = update.effective_chat
    
    if chat.type == "private":
        await update.message.reply_text(
            "👋 Привет! Добавь меня в группу, и я буду доступен там.\n\n"
            "📌 Команды в группе:\n\n"
            "🎲 РАЗВЛЕЧЕНИЯ:\n"
            "/sex - выбрать двух участников для взрослых забав\n"
            "/kiss - поцеловать двух участников\n"
            "/fight - битва двух участников\n"
            "/marry - поженить двух участников\n"
            "/slap - дать пощёчину\n"
            "/hug - обнять участника\n\n"
            "😈 ПРИКОЛЫ:\n"
            "/roast - подколоть участника\n"
            "/whip - наказать участника\n"
            "/betray - найти предателя\n"
            "/drink - выбрать, кто покупает алкоголь\n"
            "/penis - кикнуть себя из группы\n\n"
            "📸 ФОТО:\n"
            "/photo - отправить случайное фото из группы\n"
            "/collect_photos - собрать все фото из истории"
        )
    else:
        await update.message.reply_text(
            "👋 Привет! Я бот для этой группы.\n\n"
            "📌 Доступные команды:\n\n"
            "🎲 РАЗВЛЕЧЕНИЯ:\n"
            "/sex - выбрать двух участников\n"
            "/kiss - поцеловать участников\n"
            "/fight - битва участников\n"
            "/marry - свадьба в группе\n"
            "/slap - дать пощёчину\n"
            "/hug - обнять участника\n\n"
            "😈 ПРИКОЛЫ:\n"
            "/roast - подколоть\n"
            "/whip - наказать\n"
            "/betray - найти предателя\n"
            "/drink - выбрать покупателя алкоголя\n"
            "/penis - кикнуть себя\n\n"
            "📸 ФОТО:\n"
            "/photo - случайное фото\n"
            "/collect_photos - собрать фото\n\n"
            "⚠️ Для некоторых команд нужны права администратора!"
        )

async def collect_existing_photos(update: Update, context: CallbackContext):
    """Собирает все фото из группы при добавлении бота или по команде"""
    chat_id = update.effective_chat.id
    
    await update.message.reply_text(
        "📸 Начинаю сбор фото из этой группы...\n"
        "Это может занять некоторое время в зависимости от количества сообщений.\n"
        "После завершения сбора команда /photo будет работать.\n\n"
        "⚠️ Для доступа к старым сообщениям бот должен быть администратором!"
    )
    
    # Создаём задачу на сбор фото в фоне
    await group_utils.collect_all_group_photos(context.bot, chat_id, group_photos)
    
    photo_count = len(group_photos.get(chat_id, []))
    if photo_count > 0:
        await update.message.reply_text(
            f"✅ Сбор завершён! Найдено {photo_count} фото.\n"
            f"Теперь можно использовать команду /photo для отправки случайного фото."
        )
    else:
        await update.message.reply_text(
            "⚠️ Не найдено ни одного фото в истории группы.\n\n"
            "Возможные причины:\n"
            "1. Бот не является администратором группы (нужны права на чтение сообщений)\n"
            "2. В группе ещё нет фото\n"
            "3. Фото были отправлены до добавления бота, и бот не админ\n\n"
            "📌 Решение: сделайте бота администратором группы и повторите команду /collect_photos"
        )

async def photo_command(update: Update, context: CallbackContext):
    """Отправляет случайное фото из группы"""
    chat_id = update.effective_chat.id
    
    if chat_id not in group_photos or not group_photos[chat_id]:
        await update.message.reply_text(
            "📸 В этой группе пока нет сохранённых фото.\n\n"
            "Используйте команду /collect_photos для сбора фото из истории группы.\n\n"
            "⚠️ Для сбора старых фото бот должен быть администратором группы!"
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
    
    # Проверяем права бота
    try:
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if bot_member.status not in [ChatMember.ADMINISTRATOR, ChatMember.CREATOR]:
            await update.message.reply_text(
                "⚠️ Бот не является администратором группы!\n\n"
                "Для сбора фото из истории группы боту нужны права администратора.\n"
                "Пожалуйста, сделайте бота администратором и повторите команду."
            )
            return
    except Exception as e:
        logger.error(f"Ошибка при проверке прав бота: {e}")
    
    await update.message.reply_text(
        "📸 Начинаю сбор фото из этой группы...\n"
        "Это может занять некоторое время."
    )
    
    await group_utils.collect_all_group_photos(context.bot, chat_id, group_photos)
    
    photo_count = len(group_photos.get(chat_id, []))
    if photo_count > 0:
        await update.message.reply_text(
            f"✅ Сбор завершён! Найдено {photo_count} фото.\n"
            f"Теперь можно использовать команду /photo для отправки случайного фото."
        )
    else:
        await update.message.reply_text(
            "⚠️ Не найдено ни одного фото в истории группы.\n\n"
            "Убедитесь, что:\n"
            "1. Бот является администратором группы\n"
            "2. В группе есть фото\n"
            "3. Попробуйте отправить новое фото и повторить команду"
        )

async def sex_command(update: Update, context: CallbackContext):
    """Выбирает двух случайных участников группы и случайное действие"""
    chat_id = update.effective_chat.id
    
    # Получаем список участников чата
    members = await group_utils.get_chat_members(context.bot, chat_id, update)
    
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
                f"👥 {group_utils.get_user_display_name(non_bot_members[0])} не может совершить действие сам с собой! Добавьте в группу больше людей."
            )
            return
        else:
            await update.message.reply_text("👥 В группе нет других участников, кроме бота.")
            return
    
    # Список возможных действий
    actions = [
        f"🔥 {name1} разорвал {name2}у туза",
        f"🍆 {name1} жёстко заглотнул у {name2}а",
        f"💥 {name1} выебал во все дыры {name2}а"
    ]
    
    # Выбираем случайное действие
    message = random.choice(actions)
    
    await update.message.reply_text(message)
    logger.info(f"🔥 {message} в чате {chat_id}")

async def penis_command(update: Update, context: CallbackContext):
    """Кикает пользователя, который написал команду /penis"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # Проверяем, что команда используется в группе
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return
    
    # Проверяем права бота
    try:
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if bot_member.status not in [ChatMember.ADMINISTRATOR, ChatMember.CREATOR]:
            await update.message.reply_text(
                "⚠️ Бот не является администратором группы!\n"
                "Для кика пользователей боту нужны права администратора."
            )
            return
    except Exception as e:
        logger.error(f"Ошибка при проверке прав бота: {e}")
        await update.message.reply_text("❌ Не удалось проверить права бота.")
        return
    
    # Проверяем, не пытается ли администратор кикнуть сам себя
    try:
        user_member = await context.bot.get_chat_member(chat_id, user.id)
        
        # Не кикаем создателя группы и администраторов
        if user_member.status in [ChatMember.CREATOR, ChatMember.ADMINISTRATOR]:
            await update.message.reply_text(
                f"👑 {user.first_name}, вы администратор/создатель группы! "
                f"Бот не может вас кикнуть."
            )
            return
        
        # Кикаем пользователя
        await context.bot.ban_chat_member(chat_id, user.id)
        # Сразу разбаниваем, чтобы пользователь мог вернуться по ссылке
        await context.bot.unban_chat_member(chat_id, user.id)
        
        # Отправляем сообщение
        await update.message.reply_text(
            f"🍆 {user.first_name}, ты написал /penis и был кикнут за это! 👋"
        )
        logger.info(f"🍆 Пользователь {user.id} ({user.first_name}) кикнут за команду /penis в чате {chat_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при кике пользователя {user.id}: {e}")
        await update.message.reply_text(
            "❌ Не удалось кикнуть пользователя.\n"
            "Убедитесь, что у бота есть права: 'Ban users' (Блокировка пользователей)."
        )

async def handle_new_photo(update: Update, context: CallbackContext):
    """Сохраняет новые фото, отправленные в группу"""
    chat_id = update.effective_chat.id
    
    # Только для групп
    if update.effective_chat.type not in ["group", "supergroup"]:
        return
    
    if update.message and update.message.photo:
        file_id = update.message.photo[-1].file_id
        
        if chat_id not in group_photos:
            group_photos[chat_id] = []
        
        if file_id not in group_photos[chat_id]:
            group_photos[chat_id].append(file_id)
            logger.info(f"📸 Сохранено новое фото в чате {chat_id}")

async def status_handler(update: Update, context: CallbackContext):
    """Обрабатывает добавление бота в группу"""
    if not update.my_chat_member:
        return
    
    status = update.my_chat_member.new_chat_member.status
    chat_id = update.my_chat_member.chat.id
    
    if status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR]:
        logger.info(f"✅ Бот добавлен в группу {chat_id}")
        
        # Проверяем права
        is_admin = status == ChatMember.ADMINISTRATOR
        
        admin_notice = ""
        if not is_admin:
            admin_notice = "\n\n⚠️ Для сбора старых фото и кика пользователей боту нужны права администратора!"
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"👋 Привет! Я бот для этой группы.\n\n"
                 f"📌 Доступные команды:\n"
                 f"/photo - отправить случайное фото из этой группы\n"
                 f"/sex - выбрать двух случайных участников\n"
                 f"/penis - кикнуть себя из группы (только для обычных участников)\n"
                 f"/collect_photos - собрать все фото из истории группы{admin_notice}\n\n"
                 f"📸 Для работы /photo сначала необходимо собрать фото командой /collect_photos"
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
    app.add_handler(CommandHandler("penis", penis_command))
    app.add_handler(CommandHandler("collect_photos", collect_photos_command))
    
    # НОВЫЕ КОМАНДЫ
    app.add_handler(CommandHandler("drink", drink_command))
    app.add_handler(CommandHandler("kiss", kiss_command))
    app.add_handler(CommandHandler("fight", fight_command))
    app.add_handler(CommandHandler("marry", marry_command))
    app.add_handler(CommandHandler("roast", roast_command))
    app.add_handler(CommandHandler("whip", whip_command))
    app.add_handler(CommandHandler("slap", slap_command))
    app.add_handler(CommandHandler("hug", hug_command))
    app.add_handler(CommandHandler("betray", betray_command))
    app.add_handler(CommandHandler("porno", porno_command))
    
    # Обработчики
    app.add_handler(MessageHandler(filters.PHOTO, handle_new_photo))
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
