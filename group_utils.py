import logging
import asyncio
from typing import List, Dict, Optional
from telegram import Bot, ChatMember, User, Update

logger = logging.getLogger(__name__)

async def get_chat_members(bot: Bot, chat_id: int, update: Update = None) -> List[User]:
    """
    Получает список всех участников чата (не только админов)
    """
    members = []
    user_ids = set()
    
    try:
        # 1. Получаем администраторов
        admins = await bot.get_chat_administrators(chat_id)
        for admin in admins:
            if admin.user.id != bot.id and admin.user.id not in user_ids:
                user_ids.add(admin.user.id)
                members.append(admin.user)
        
        logger.info(f"Найдено {len(admins)} администраторов в чате {chat_id}")
        
        # 2. Пытаемся получить список всех участников (для супергрупп)
        try:
            # Для супергрупп можно получить до 200 участников через get_chat
            chat = await bot.get_chat(chat_id)
            
            # Если это супергруппа, пробуем получить участников через get_chat_members
            if chat.type in ["supergroup", "group"]:
                # Получаем первых 200 участников (максимум, который дает Telegram API)
                async for member in bot.get_chat_members(chat_id, limit=200):
                    if member.user.id != bot.id and member.user.id not in user_ids:
                        user_ids.add(member.user.id)
                        members.append(member.user)
                        if len(members) >= 200:  # Ограничиваем для производительности
                            break
                logger.info(f"Получено {len(members)} участников через get_chat_members")
        except Exception as e:
            logger.warning(f"Не удалось получить всех участников через get_chat_members: {e}")
        
        # 3. Собираем участников из последних сообщений (если нужно больше)
        if len(members) < 10 and update and update.effective_chat:
            try:
                # Получаем последние 500 сообщений для сбора активных пользователей
                active_users = set()
                async for message in bot.get_chat_history(chat_id, limit=500):
                    # Добавляем автора сообщения
                    if message.from_user and message.from_user.id != bot.id:
                        active_users.add(message.from_user.id)
                    
                    # Добавляем того, кому отвечают
                    if message.reply_to_message and message.reply_to_message.from_user:
                        if message.reply_to_message.from_user.id != bot.id:
                            active_users.add(message.reply_to_message.from_user.id)
                    
                    # Добавляем упомянутых пользователей
                    if message.entities:
                        for entity in message.entities:
                            if entity.type == "mention" and message.text:
                                pass  # Сложно получить пользователя по mention
                
                # Получаем информацию о пользователях
                for user_id in active_users:
                    if user_id not in user_ids:
                        try:
                            user = await bot.get_chat_member(chat_id, user_id)
                            user_ids.add(user_id)
                            members.append(user.user)
                        except:
                            pass
                
                logger.info(f"Добавлено {len(active_users)} активных пользователей из истории")
            except Exception as e:
                logger.warning(f"Не удалось собрать участников из истории: {e}")
        
        # 4. Добавляем отправителя текущего сообщения, если его ещё нет
        if update and update.effective_message and update.effective_message.from_user:
            if update.effective_message.from_user.id not in user_ids:
                user_ids.add(update.effective_message.from_user.id)
                members.append(update.effective_message.from_user)
        
        # 5. Для обычных групп (не супергрупп) пытаемся получить участников через разные методы
        if len(members) < 3:
            try:
                # Пробуем получить участников через get_chat_administrators (уже сделали)
                # Пробуем получить приглашённых пользователей
                chat = await bot.get_chat(chat_id)
                if chat.invite_link:
                    logger.info("У группы есть инвайт-ссылка, но получить участников по ней нельзя")
            except:
                pass
        
    except Exception as e:
        logger.error(f"Ошибка при получении участников чата {chat_id}: {e}")
    
    # Удаляем дубликаты (на всякий случай)
    unique_members = []
    seen_ids = set()
    for member in members:
        if member.id not in seen_ids:
            seen_ids.add(member.id)
            unique_members.append(member)
    
    members = unique_members
    
    # Логируем результат
    logger.info(f"Всего собрано {len(members)} уникальных участников в чате {chat_id}")
    
    # Если всё ещё нет участников, создаём заглушку для тестирования
    if len(members) < 2:
        logger.warning(f"Недостаточно участников в чате {chat_id}, используются тестовые данные")
        # Создаём тестовых пользователей, если нет реальных
        if not members:
            members.append(User(id=1, first_name="Участник1", is_bot=False))
            members.append(User(id=2, first_name="Участник2", is_bot=False))
            members.append(User(id=3, first_name="Участник3", is_bot=False))
        elif len(members) == 1:
            members.append(User(id=3, first_name="Участник3", is_bot=False))
    
    return members

async def collect_all_group_photos(bot: Bot, chat_id: int, storage: Dict[int, List[str]], limit: int = 500):
    """
    Собирает все фото из истории группы
    """
    if chat_id not in storage:
        storage[chat_id] = []
    
    collected = set(storage[chat_id])
    processed = 0
    last_message_id = None
    
    logger.info(f"Начинаем сбор фото в чате {chat_id}")
    
    try:
        while processed < limit:
            try:
                # Получаем сообщения из чата
                if last_message_id:
                    messages = await bot.get_chat_history(
                        chat_id=chat_id,
                        limit=min(100, limit - processed),
                        until_message_id=last_message_id
                    )
                else:
                    messages = await bot.get_chat_history(
                        chat_id=chat_id,
                        limit=min(100, limit - processed)
                    )
                
                if not messages:
                    break
                
                for message in messages:
                    processed += 1
                    
                    # Проверяем наличие фото
                    if message.photo:
                        file_id = message.photo[-1].file_id
                        if file_id not in collected:
                            collected.add(file_id)
                            storage[chat_id].append(file_id)
                            logger.debug(f"Найдено фото {file_id} в сообщении {message.message_id}")
                    
                    # Сохраняем ID последнего сообщения для пагинации
                    last_message_id = message.message_id
                
                if len(messages) < 100:
                    break
                    
                # Небольшая задержка, чтобы не превысить лимиты API
                await asyncio.sleep(0.3)
                
            except Exception as e:
                logger.error(f"Ошибка при сборе сообщений в чате {chat_id}: {e}")
                break
                
    except Exception as e:
        logger.error(f"Ошибка при сборе фото в чате {chat_id}: {e}")
    
    logger.info(f"Сбор фото в чате {chat_id} завершён. Найдено {len(storage[chat_id])} фото")
    return storage[chat_id]

def get_user_display_name(user: User) -> str:
    """
    Возвращает отображаемое имя пользователя
    """
    if user.username:
        return f"@{user.username}"
    elif user.full_name:
        return user.full_name
    else:
        return f"Пользователь {user.id}"

def save_photos_to_file(chat_id: int, storage: Dict[int, List[str]], filename: str = None):
    """
    Сохраняет список фото в файл (опционально)
    """
    import json
    
    if filename is None:
        filename = f"group_photos_{chat_id}.json"
    
    if chat_id in storage:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(storage[chat_id], f, ensure_ascii=False, indent=2)
        logger.info(f"Сохранено {len(storage[chat_id])} фото в {filename}")
        return True
    return False

def load_photos_from_file(chat_id: int, storage: Dict[int, List[str]], filename: str = None):
    """
    Загружает список фото из файла (опционально)
    """
    import json
    import os
    
    if filename is None:
        filename = f"group_photos_{chat_id}.json"
    
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            photos = json.load(f)
            storage[chat_id] = photos
            logger.info(f"Загружено {len(photos)} фото из {filename}")
            return True
    return False

async def test_bot_permissions(bot: Bot, chat_id: int) -> dict:
    """
    Проверяет права бота в группе
    """
    try:
        bot_member = await bot.get_chat_member(chat_id, bot.id)
        chat = await bot.get_chat(chat_id)
        
        return {
            "is_admin": bot_member.status in [ChatMember.ADMINISTRATOR, ChatMember.CREATOR],
            "can_read_messages": bot_member.status != ChatMember.RESTRICTED,
            "status": bot_member.status,
            "chat_type": chat.type
        }
    except Exception as e:
        logger.error(f"Ошибка при проверке прав: {e}")
        return {
            "is_admin": False,
            "can_read_messages": False,
            "status": "unknown",
            "error": str(e)
        }
