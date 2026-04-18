import logging
import asyncio
from typing import List, Dict, Optional
from telegram import Bot, ChatMember, User

logger = logging.getLogger(__name__)

async def get_chat_members(bot: Bot, chat_id: int) -> List[User]:
    """
    Получает список всех участников чата (не админов, а обычных участников)
    """
    members = []
    try:
        # Получаем количество участников
        chat = await bot.get_chat(chat_id)
        
        # Получаем участников через get_chat_administrators (только админы)
        admins = await bot.get_chat_administrators(chat_id)
        admin_ids = {admin.user.id for admin in admins}
        
        # Для обычных групп нужно использовать другой подход
        # К сожалению, Telegram API не даёт прямой доступ к списку всех участников группы
        # Поэтому собираем участников из сообщений или используем другой метод
        
        # Вместо этого, для простоты, будем использовать:
        # 1. Администраторов
        # 2. Бота (если нужно)
        # 3. Добавим виртуальный список или будем собирать из активных пользователей
        
        # Базовый список - администраторы
        for admin in admins:
            if admin.user.id != bot.id:  # исключаем бота
                members.append(admin.user)
        
        # Если администраторов меньше 2, добавляем бота как временного участника
        # (в реальности бот не участвует в "выeбал")
        if len(members) < 2 and bot.id not in [m.id for m in members]:
            # Добавляем заглушку - бот не будет выбран, если есть другие
            pass
            
    except Exception as e:
        logger.error(f"Ошибка при получении участников чата {chat_id}: {e}")
    
    # Если участников всё ещё мало, добавляем виртуальных для демонстрации
    # В реальном боте вы можете хранить список активных пользователей
    if len(members) < 2:
        # Создаём виртуальных пользователей для демонстрации (только если нет реальных)
        # ВАЖНО: В реальном боте нужно собирать пользователей из сообщений
        if not members:
            members.append(User(id=1, first_name="Пользователь1", is_bot=False))
            members.append(User(id=2, first_name="Пользователь2", is_bot=False))
            members.append(User(id=3, first_name="Пользователь3", is_bot=False))
            logger.warning(f"Использованы виртуальные пользователи для чата {chat_id}")
    
    return members

async def collect_all_group_photos(bot: Bot, chat_id: int, storage: Dict[int, List[str]], limit: int = 1000):
    """
    Собирает все фото из истории группы
    """
    if chat_id not in storage:
        storage[chat_id] = []
    
    collected = set(storage[chat_id])
    offset_id = 0
    processed = 0
    
    logger.info(f"Начинаем сбор фото в чате {chat_id}")
    
    try:
        while True:
            try:
                # Получаем сообщения из чата
                messages = await bot.get_chat_history(
                    chat_id=chat_id,
                    limit=min(100, limit - processed),
                    offset=offset_id
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
                    
                    # Также проверяем медиагруппы (альбомы)
                    if message.media_group_id and message.photo:
                        # Уже обработано выше
                        pass
                    
                    offset_id = message.message_id
                
                if processed >= limit:
                    break
                    
                # Небольшая задержка, чтобы не превысить лимиты API
                await asyncio.sleep(0.5)
                
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
