"""
Telegram бот для управления дедлайнами.

Основные команды:
- /start - регистрация пользователя
- /help - справка
- /register - привязка email/ника к Telegram аккаунту
- /my_deadlines - показать личные дедлайны
- /subscribe - подписка/отписка от уведомлений
"""

import asyncio
import json
import logging
import os
import sys
from datetime import UTC, datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from dotenv import load_dotenv

from db import init_db
from logging_config import setup_logging, log_startup_info, log_error_with_context
from notifications import (
    check_and_notify_deadlines,
    get_deadlines_at_halfway,
    send_message_to_all_subscribers,
)
from services import (
    approve_deadline_verification,
    format_deadline,
    get_all_subscribed_users,
    get_or_create_user,
    get_pending_verifications,
    get_user_by_telegram_id,
    get_user_deadlines,
    get_user_subscription,
    reject_deadline_verification,
    request_deadline_verification,
    toggle_subscription,
    update_user_email,
)
from scripts.sync_deadlines import sync_all_deadlines, sync_user_deadlines
from block_utils import is_user_blocked, block_user, unblock_user, get_blocked_users
from models import DeadlineStatus
from notification_settings import (
    get_notification_summary,
    get_user_notification_settings,
    update_user_notification_settings,
    parse_weekly_days,
    format_weekly_days,
    reset_user_notification_settings,
)

# Настройка логирования
logger = setup_logging(os.getenv("LOG_LEVEL", "INFO"))

# Загружаем переменные окружения
load_dotenv()

# Получаем токен бота
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN не задан в переменных окружения!")
    sys.exit(1)

# Для обратной совместимости
TELEGRAM_BOT_TOKEN = BOT_TOKEN

# Получаем интервал обновления из переменных окружения (по умолчанию 30 минут)
UPDATE_INTERVAL_MINUTES = int(os.getenv("UPDATE_INTERVAL_MINUTES", "30"))

# Получаем URL базы данных
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///../data/deadlines.db")

# Получаем список ID администраторов из переменных окружения
# Формат: "123456789,987654321" (через запятую)
ADMIN_IDS_STR = os.getenv("TELEGRAM_ADMIN_IDS", "")
ADMIN_IDS = set()
if ADMIN_IDS_STR:
    try:
        ADMIN_IDS = {int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(",") if admin_id.strip()}
        logger.info(f"Загружено {len(ADMIN_IDS)} администраторов")
    except ValueError as e:
        logger.warning(f"Ошибка при парсинге TELEGRAM_ADMIN_IDS: {e}")

# Настройка часового пояса (GMT+3, Moscow)
MOSCOW_TZ = timezone(timedelta(hours=3))

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# Глобальное хранилище состояний пользователей для настройки уведомлений
user_settings_states = {}  # telegram_id -> state


async def block_check_middleware(handler, event, data):
    """
    Middleware для проверки блокировки пользователей.

    Заблокированные пользователи не смогут использовать никаких команд бота.
    """
    # Получаем информацию о пользователе
    if hasattr(event, 'from_user') and event.from_user:
        telegram_id = event.from_user.id

        # Проверяем, заблокирован ли пользователь
        if is_user_blocked(telegram_id):
            logger.warning(f"Заблокированный пользователь {telegram_id} попытался использовать бота")
            # Не отвечаем заблокированным пользователям
            return

    # Продолжаем обработку для незаблокированных пользователей
    return await handler(event, data)

# Инициализация планировщика
scheduler = AsyncIOScheduler()


def is_admin(telegram_id: int) -> bool:
    """
    Проверить, является ли пользователь администратором.

    Args:
        telegram_id: Telegram ID пользователя

    Returns:
        True если пользователь администратор, False в противном случае
    """
    return telegram_id in ADMIN_IDS


def get_current_time_moscow() -> datetime:
    """
    Получить текущее время в московском часовом поясе.

    Returns:
        datetime в часовом поясе Moscow (GMT+3)
    """
    return datetime.now(MOSCOW_TZ)


def format_datetime_moscow(dt: datetime) -> str:
    """
    Форматировать дату и время в московском часовом поясе.

    Args:
        dt: datetime объект (может быть naive или с timezone)

    Returns:
        Отформатированная строка в Moscow timezone
    """
    if dt.tzinfo is None:
        # Если naive datetime, предполагаем UTC и конвертируем
        dt = dt.replace(tzinfo=UTC)

    # Конвертируем в Moscow timezone
    moscow_time = dt.astimezone(MOSCOW_TZ)
    return moscow_time.strftime("%d.%m.%Y %H:%M")


def escape_markdown(text: str) -> str:
    """
    Экранировать специальные символы Markdown в тексте.
    
    Args:
        text: Текст для экранирования
        
    Returns:
        Экранированный текст
    """
    # Символы, которые нужно экранировать в Markdown
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, '\\' + char)
    return text


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Обработчик команды /start - регистрация пользователя."""
    try:
        user = get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )

        user_info = []
        if user.email:
            user_info.append(f"📧 Email: {user.email}")
        if user.username:
            user_info.append(f"👤 Ник: {user.username}")

        user_info_str = " (" + ", ".join(user_info) + ")" if user_info else ""

        # Определяем статус регистрации
        if user.username:
            status_text = f"Статус: зарегистрирован{user_info_str}"
        else:
            status_text = "Статус: зарегистрирован (требуется привязать ник для получения дедлайнов)"

        welcome_text = (
            f"👋 Привет, {message.from_user.first_name or 'пользователь'}!\n\n"
            f"Я бот для управления дедлайнами из Yonote.\n\n"
            f"Твой ID в системе: {user.id}\n"
            f"Telegram ID: {user.telegram_id}\n"
            f"{status_text}\n\n"
        )

        welcome_text += (
            "Доступные команды:\n"
            "/help - справка по командам\n"
            "/register - привязать ник\n"
            "/logout - отписаться от уведомлений и сбросить данные\n"
            "/my_deadlines - показать мои дедлайны\n"
            "/subscribe - управление подписками"
        )

        # Создаем клавиатуру с основными командами
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Регистрация", callback_data="cmd_register"),
                InlineKeyboardButton(text="🔄 Синхронизация", callback_data="cmd_sync")
            ],
            [
                InlineKeyboardButton(text="📅 Мои дедлайны", callback_data="cmd_my_deadlines"),
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="cmd_notifications")
            ]
        ])

        await message.answer(welcome_text, reply_markup=keyboard)
        logger.info(f"Пользователь {user.telegram_id} зарегистрирован/обновлён")
    except Exception as e:
        logger.error(f"Ошибка при регистрации пользователя: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при регистрации. Попробуйте позже.")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Обработчик команды /help - справка."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="cmd_start") 
            ]
    ])
    help_text = (
        "📚 *Справка по командам бота*\n\n"
        "*/start* - Регистрация в системе\n"
        "*/help* - Показать эту справку\n"
        "*/register* - Привязать ник к аккаунту\n"
        "   Использование: `/register username`\n"
        "*/logout* - Отписаться от уведомлений и сбросить данные\n"
        "*/my_deadlines* - Показать все ваши дедлайны\n"
        "*/sync* - Синхронизировать дедлайны из Yonote вручную\n"
        "*/notifications* - Настройки персональных уведомлений\n"
        "*/subscribe* - Включить/выключить уведомления о дедлайнах\n"
        "*/broadcast* - Отправить сообщение всем подписанным (только для администраторов)\n"
        "   Использование: `/broadcast текст сообщения`\n"
        "*/subscribers* - Показать список всех подписанных (только для администраторов)\n"
        "*/test_halfway* - Проверить напоминания за половину срока (только для администраторов)\n"
        "*/check_notifications* - Ручная проверка и отправка уведомлений (только для администраторов)\n"
        "*/block* - Заблокировать пользователя (только для администраторов)\n"
        "   Использование: `/block telegram_id`\n"
        "*/unblock* - Разблокировать пользователя (только для администраторов)\n"
        "   Использование: `/unblock telegram_id`\n"
        "*/blocked_users* - Показать список заблокированных пользователей (только для администраторов)\n\n"
        "💡 *Совет*: После регистрации привяжите ваш ник, "
        "чтобы получать персональные дедлайны. Используйте /sync для немедленной синхронизации."
    )
    await message.answer(help_text, parse_mode="Markdown", reply_markup=keyboard)


@router.message(Command("register"))
async def cmd_register(message: Message) -> None:
    """Обработчик команды /register - привязка ника."""
    try:
        # Получаем аргументы команды
        command_args = message.text.split(maxsplit=1) if message.text else []
        if len(command_args) < 2:
            await message.answer(
                "❌ Укажите ник для привязки.\n\n"
                "Пример:\n"
                "`/register username`",
                parse_mode="Markdown",
            )
            return

        # Прячем @ если пользователь ввел его
        identifier = command_args[1].strip().lstrip('@')

        user = get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer(
                "❌ Вы не зарегистрированы. Сначала выполните команду /start"
            )
            return

        # Сохраняем в username
        user.username = identifier
        from db import SessionLocal

        session = SessionLocal()
        try:
            session.add(user)
            session.commit()
            await message.answer(
                f"✅ Ник успешно привязан: {identifier}\n\n"
                f"Теперь вы будете получать дедлайны, связанные с этим ником."
            )
            logger.info(f"Пользователь {user.telegram_id} привязал ник: {identifier}")
        finally:
            session.close()

    except Exception as e:
        logger.error(f"Ошибка при регистрации ника: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(Command("my_deadlines"))
async def cmd_my_deadlines(message: Message) -> None:
    """Обработчик команды /my_deadlines - показать дедлайны пользователя."""
    try:
        user = get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer(
                "❌ Вы не зарегистрированы. Сначала выполните команду /start"
            )
            return

        # Проверяем, что пользователь зарегистрировал ник для Yonote
        if not user.username:
            await message.answer(
                "❌ Вы не зарегистрировали ник для получения дедлайнов.\n\n"
                "💡 Используйте команду `/register your_yonote_nickname`, "
                "чтобы привязать ваш ник из Yonote и получить доступ к дедлайнам.",
                parse_mode="Markdown"
            )
            return

        # Сначала синхронизируем дедлайны из Yonote
        await message.answer("🔄 Синхронизирую дедлайны из Yonote...")
        try:
            from scripts.sync_deadlines import sync_user_deadlines
            created, updated = await sync_user_deadlines(user)
            sync_message = f"✅ Синхронизация завершена: создано {created}, обновлено {updated}"
            logger.info(f"Синхронизация для /my_deadlines: создано {created}, обновлено {updated}")
        except Exception as sync_error:
            sync_message = f"⚠️ Ошибка при синхронизации: {sync_error}"
            logger.error(f"Ошибка при синхронизации в /my_deadlines: {sync_error}", exc_info=True)

        deadlines = get_user_deadlines(user.id, status="active", only_future=True, include_no_date=True)

        # Дополнительная фильтрация прошедших дедлайнов на уровне Python
        # (на случай, если в БД есть проблемы с часовыми поясами)
        now = datetime.now(UTC)
        filtered_deadlines = []
        for d in deadlines:
            # Включаем дедлайны без даты (они уже отфильтрованы в get_user_deadlines если нужно)
            if d.due_date is None:
                filtered_deadlines.append(d)  # Добавляем дедлайны без даты
                continue

            # Убеждаемся, что дата имеет timezone (если нет - добавляем UTC)
            due_date = d.due_date
            if due_date.tzinfo is None:
                due_date = due_date.replace(tzinfo=UTC)
                logger.debug(f"Дедлайн '{d.title}' без timezone - добавлен UTC")

            if due_date < now:
                logger.info(f"Дедлайн '{d.title}' прошел ({due_date} < {now}) - пропускаем")
                continue
            filtered_deadlines.append(d)
        deadlines = filtered_deadlines

        if not deadlines:
            user_info = []
            if user.email:
                user_info.append(f"📧 Email: {user.email}")
            if user.username:
                user_info.append(f"👤 Ник: {user.username}")

            info_text = "\n".join(user_info) if user_info else "не задан"

            await message.answer(
                f"{sync_message}\n\n"
                "📭 У вас пока нет активных дедлайнов.\n\n"
                f"Ваш идентификатор: {info_text}\n\n"
                "💡 Попробуйте:\n"
                "• Использовать команду /sync для ручной синхронизации\n"
                "• Убедиться, что в Yonote есть дедлайны для вашего аккаунта\n\n"
                "Дедлайны также автоматически синхронизируются каждые 30 минут."
            )
            return

        # Формируем сообщение с дедлайнами и кнопками
        response_lines = [f"{sync_message}\n\n📋 *Ваши дедлайны ({len(deadlines)}):*\n"]

        # Создаем клавиатуру с кнопками для каждого дедлайна
        keyboard_buttons = []
        
        for i, deadline in enumerate(deadlines, 1):
            # Экранируем заголовок дедлайна
            escaped_title = escape_markdown(deadline.title)
            
            # Показываем статус дедлайна
            status_emoji = "⏳" if deadline.status == DeadlineStatus.PENDING_VERIFICATION else "🟢"
            response_lines.append(f"\n*{i}. {status_emoji} {escaped_title}*")
            
            if deadline.due_date:
                due_date_str = deadline.due_date.strftime("%d.%m.%Y %H:%M")
                response_lines.append(f"⏰ {due_date_str}")
            if deadline.description:
                desc = deadline.description[:100] + "..." if len(deadline.description) > 100 else deadline.description
                escaped_desc = escape_markdown(desc)
                response_lines.append(f"📝 {escaped_desc}")
            
            # Добавляем кнопку подтверждения только для активных дедлайнов
            if deadline.status == DeadlineStatus.ACTIVE:
                # Ограничиваем длину текста кнопки (максимум 64 символа для Telegram)
                button_text = f"✅ Выполнен #{i}"
                if len(button_text) > 64:
                    button_text = f"✅ #{i}"
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=f"complete_deadline_{deadline.id}"
                    )
                ])
            elif deadline.status == DeadlineStatus.PENDING_VERIFICATION:
                response_lines.append("⏳ *На проверке у администратора*")

        # Добавляем информацию внизу того же сообщения
        user_nick = user.username or user.email or "не указан"
        escaped_nick = escape_markdown(user_nick)

        # Определяем, есть ли дедлайны с датой и какие даты ближайшие
        deadlines_with_date = [d for d in deadlines if d.due_date]

        response_lines.append("\n" + "─" * 20)
        response_lines.append(f"👤 *Ник:* {escaped_nick}")

        if deadlines_with_date:
            # Показываем ближайший дедлайн с датой
            nearest_deadline = min(deadlines_with_date, key=lambda d: d.due_date)
            due_date_str = nearest_deadline.due_date.strftime("%d.%m.%Y %H:%M")
            response_lines.append(f"📅 *Ближайший дедлайн:* {due_date_str}")
        else:
            response_lines.append(f"📅 *Дедлайн:* нет точной даты")

        response_lines.append(f"🎵 *Песня:* -")
        response_lines.append("")
        response_lines.append("⚠️ Если что-то не успеваете — пишите админам")

        response_text = "\n".join(response_lines)

        # Создаем клавиатуру, если есть кнопки
        reply_markup = None
        if keyboard_buttons:
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        # Telegram имеет лимит на длину сообщения (4096 символов)
        if len(response_text) > 4000:
            # Разбиваем на несколько сообщений, но стараемся сохранить footer в последнем
            chunk = []
            chunk_length = 0
            footer_lines = response_lines[-5:]  # Последние 5 строк (разделитель + информация)
            main_lines = response_lines[:-5]   # Основной список дедлайнов
            
            # Сначала отправляем основной список
            for line in main_lines:
                line_length = len(line) + 1
                if chunk_length + line_length > 3800:  # Оставляем место для footer
                    await message.answer("\n".join(chunk), parse_mode="Markdown")
                    chunk = [line]
                    chunk_length = line_length
                else:
                    chunk.append(line)
                    chunk_length += line_length
            
            # Добавляем footer к последнему chunk или отправляем отдельно
            footer_text = "\n".join(footer_lines)
            if chunk_length + len(footer_text) < 4000:
                chunk.extend(footer_lines)
                await message.answer("\n".join(chunk), parse_mode="Markdown")
            else:
                    if chunk:
                        await message.answer("\n".join(chunk), parse_mode="Markdown")
                    await message.answer(footer_text, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await message.answer(response_text, parse_mode="Markdown", reply_markup=reply_markup)

        logger.info(f"Пользователь {user.telegram_id} запросил список дедлайнов: {len(deadlines)} шт.")

    except Exception as e:
        logger.error(f"Ошибка при получении дедлайнов: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при получении дедлайнов. Попробуйте позже.")


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message) -> None:
    """Обработчик команды /subscribe - управление подписками."""
    try:
        user = get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer(
                "❌ Вы не зарегистрированы. Сначала выполните команду /start"
            )
            return

        # Проверяем, что пользователь зарегистрировал ник для Yonote
        if not user.username:
            await message.answer(
                "❌ Вы не зарегистрировали ник для получения дедлайнов.\n\n"
                "💡 Используйте команду `/register your_yonote_nickname`, "
                "чтобы привязать ваш ник из Yonote и получить доступ к уведомлениям.",
                parse_mode="Markdown"
            )
            return

        subscription = toggle_subscription(user.id, notification_type="telegram")

        if subscription.active:
            status_text = "✅ Уведомления включены"
            action_text = "Вы будете получать уведомления о приближающихся дедлайнах."
        else:
            status_text = "🔕 Уведомления выключены"
            action_text = "Вы больше не будете получать уведомления."

        await message.answer(
            f"{status_text}\n\n{action_text}\n\n"
            f"Используйте команду /subscribe снова, чтобы изменить настройки."
        )

        logger.info(
            f"Пользователь {user.telegram_id} {'включил' if subscription.active else 'выключил'} подписку"
        )

    except Exception as e:
        logger.error(f"Ошибка при изменении подписки: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(Command("logout"))
async def cmd_logout(message: Message) -> None:
    """Обработчик команды /logout - удаление данных пользователя."""
    try:
        user = get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer(
                "❌ Вы не зарегистрированы. Нечего удалять."
            )
            return

        user_info = []
        if user.email:
            user_info.append(f"📧 Email: {user.email}")
        if user.username:
            user_info.append(f"👤 Ник: {user.username}")

        user_info_str = ", ".join(user_info)
        if user_info_str:
            user_info_str = f" ({user_info_str})"

        # Удаляем пользователя из базы (каскадно удалятся дедлайны и подписки)
        from services import delete_user
        success = delete_user(user.id)

        if success:
            await message.answer(
                f"✅ Вы успешно отписались от уведомлений и сбросили данные{user_info_str}.\n\n"
                f"Все ваши данные были удалены из системы."
            )
            logger.info(f"Пользователь {user.telegram_id} вышел из системы")
        else:
            await message.answer("❌ Произошла ошибка при удалении данных.")
            logger.error(f"Ошибка при удалении пользователя {user.telegram_id}")

    except Exception as e:
        logger.error(f"Ошибка при выходе из системы: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(Command("sync"))
async def cmd_sync(message: Message) -> None:
    """Обработчик команды /sync - ручная синхронизация дедлайнов."""
    try:
        user = get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer(
                "❌ Вы не зарегистрированы. Сначала выполните команду /start"
            )
            return

        # Проверяем, что пользователь зарегистрировал ник для Yonote
        if not user.username:
            await message.answer(
                "❌ Вы не зарегистрировали ник для получения дедлайнов.\n\n"
                "💡 Используйте команду `/register your_yonote_nickname`, "
                "чтобы привязать ваш ник из Yonote и синхронизировать дедлайны.",
                parse_mode="Markdown"
            )
            return

        await message.answer("🔄 Начинаю синхронизацию дедлайнов из Yonote...")

        # Синхронизируем дедлайны для текущего пользователя
        created, updated = await sync_user_deadlines(user)

        # После синхронизации проверяем уведомления
        logger.info(f"Проверка уведомлений после ручной синхронизации для пользователя {user.id}")
        notification_stats = await check_and_notify_deadlines(bot)

        result_text = (
            f"✅ Синхронизация завершена!\n\n"
            f"📊 Статистика:\n"
            f"• Создано новых дедлайнов: {created}\n"
            f"• Обновлено дедлайнов: {updated}\n"
            f"• Уведомлений отправлено: {notification_stats['notifications_sent']}\n\n"
        )

        if created == 0 and updated == 0:
            result_text += (
                "💡 Если дедлайны не появились, проверьте:\n"
                "• Есть ли дедлайны в Yonote для вашего аккаунта\n"
                "• Настройки YONOTE_CALENDAR_ID в .env"
            )

        await message.answer(result_text)
        logger.info(
            f"Пользователь {user.telegram_id} выполнил ручную синхронизацию: "
            f"создано {created}, обновлено {updated}"
        )

    except Exception as e:
        logger.error(f"Ошибка при синхронизации: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при синхронизации: {e}\n\n"
            "Проверьте логи бота для подробностей."
        )


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message) -> None:
    """Обработчик команды /broadcast - отправить сообщение всем подписанным (только для администраторов)."""
    # Проверяем права администратора
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer(
            "❌ У вас нет прав для выполнения этой команды.\n\n"
            "Эта команда доступна только администраторам."
        )
        logger.warning(
            f"Пользователь {message.from_user.id if message.from_user else 'unknown'} "
            f"попытался выполнить команду /broadcast без прав администратора"
        )
        return

    try:
        # Получаем текст сообщения после команды
        command_args = message.text.split(maxsplit=1) if message.text else []
        if len(command_args) < 2:
            await message.answer(
                "❌ Укажите текст сообщения для рассылки.\n\n"
                "Пример:\n"
                "`/broadcast Важное объявление для всех!`",
                parse_mode="Markdown",
            )
            return

        broadcast_text = command_args[1].strip()

        await message.answer("🔄 Начинаю рассылку сообщения всем подписанным...")

        # Отправляем сообщение всем подписанным
        stats = await send_message_to_all_subscribers(bot, broadcast_text)

        result_text = (
            f"✅ Рассылка завершена!\n\n"
            f"📊 Статистика:\n"
            f"• Всего подписанных: {stats['total_subscribers']}\n"
            f"• Отправлено успешно: {stats['sent']}\n"
            f"• Ошибок: {stats['failed']}"
        )

        await message.answer(result_text)
        logger.info(
            f"Пользователь {message.from_user.id} выполнил рассылку: "
            f"отправлено {stats['sent']} из {stats['total_subscribers']}"
        )

    except Exception as e:
        logger.error(f"Ошибка при рассылке: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при рассылке: {e}\n\n"
            "Проверьте логи бота для подробностей."
        )


@router.message(Command("subscribers"))
async def cmd_subscribers(message: Message) -> None:
    """Обработчик команды /subscribers - показать список всех подписанных (только для администраторов)."""
    # Проверяем права администратора
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer(
            "❌ У вас нет прав для выполнения этой команды.\n\n"
            "Эта команда доступна только администраторам."
        )
        logger.warning(
            f"Пользователь {message.from_user.id if message.from_user else 'unknown'} "
            f"попытался выполнить команду /subscribers без прав администратора"
        )
        return

    try:
        # Получаем всех подписанных пользователей
        subscribed_users = get_all_subscribed_users(notification_type="telegram")

        if not subscribed_users:
            await message.answer("📭 Нет подписанных пользователей.")
            return

        # Формируем список подписанных
        lines = [f"👥 *Список подписанных пользователей* ({len(subscribed_users)}):\n"]

        for idx, (user, subscription) in enumerate(subscribed_users, 1):
            username_display = escape_markdown(user.username) if user.username else "не указан"
            telegram_id = user.telegram_id
            created_at = subscription.created_at.strftime("%d.%m.%Y %H:%M") if subscription.created_at else "неизвестно"

            user_info = (
                f"{idx}\\. *Ник:* {username_display}\n"
                f"   Telegram ID: `{telegram_id}`\n"
                f"   Подписка создана: {created_at}"
            )
            lines.append(user_info)

        # Разбиваем на части, если сообщение слишком длинное
        full_text = "\n\n".join(lines)
        max_length = 4096  # Лимит Telegram

        if len(full_text) <= max_length:
            await message.answer(full_text, parse_mode="Markdown")
        else:
            # Отправляем частями
            current_text = lines[0] + "\n\n"
            for line in lines[1:]:
                if len(current_text + line + "\n\n") > max_length:
                    await message.answer(current_text, parse_mode="Markdown")
                    current_text = line + "\n\n"
                else:
                    current_text += line + "\n\n"

            if current_text.strip():
                await message.answer(current_text, parse_mode="Markdown")

        logger.info(
            f"Администратор {message.from_user.id} запросил список подписанных: "
            f"найдено {len(subscribed_users)} пользователей"
        )

    except Exception as e:
        logger.error(f"Ошибка при получении списка подписанных: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при получении списка подписанных: {e}\n\n"
            "Проверьте логи бота для подробностей."
        )


@router.message(Command("test_halfway"))
async def cmd_test_halfway(message: Message) -> None:
    """Обработчик команды /test_halfway - проверить напоминания за половину срока (только для администраторов)."""
    # Проверяем права администратора
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer(
            "❌ У вас нет прав для выполнения этой команды.\n\n"
            "Эта команда доступна только администраторам."
        )
        logger.warning(
            f"Пользователь {message.from_user.id if message.from_user else 'unknown'} "
            f"попытался выполнить команду /test_halfway без прав администратора"
        )
        return

    try:
        user = get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer("❌ Пользователь не найден. Используйте /start для регистрации.")
            return

        # Проверяем, что пользователь зарегистрировал ник для Yonote
        if not user.username:
            await message.answer(
                "❌ Вы не зарегистрировали ник для получения дедлайнов.\n\n"
                "💡 Используйте команду `/register your_yonote_nickname`, "
                "чтобы привязать ваш ник из Yonote и синхронизировать дедлайны.",
                parse_mode="Markdown"
            )
            return

        # Сначала синхронизируем дедлайны из Yonote
        await message.answer("🔄 Синхронизирую дедлайны из Yonote...")
        try:
            created, updated = await sync_user_deadlines(user)
            sync_message = f"✅ Синхронизация завершена: создано {created}, обновлено {updated}"
            logger.info(f"Синхронизация для /test_halfway: создано {created}, обновлено {updated}")
        except Exception as e:
            sync_message = f"⚠️ Ошибка при синхронизации: {e}"
            logger.error(f"Ошибка при синхронизации в /test_halfway: {e}", exc_info=True)

        # Получаем все активные дедлайны пользователя
        from services import get_user_deadlines

        deadlines = get_user_deadlines(user.id, status=DeadlineStatus.ACTIVE, only_future=True)

        if not deadlines:
            await message.answer(
                f"{sync_message}\n\n"
                "📭 У вас нет активных дедлайнов для проверки.\n\n"
                "Создайте дедлайн или синхронизируйте их из Yonote с помощью /sync."
            )
            return

        # Проверяем, какие дедлайны на половине срока
        halfway_deadlines = get_deadlines_at_halfway(deadlines)

        now = get_current_time_moscow()
        lines = [
            f"⏳ *Проверка напоминаний за половину срока*\n",
            f"{sync_message}\n",
            f"Текущее время: {now.strftime('%d.%m.%Y %H:%M:%S (MSK)')}\n",
            f"Всего активных дедлайнов: {len(deadlines)}\n",
            f"На половине срока: {len(halfway_deadlines)}\n",
            f"\n📊 *Как рассчитывается половина срока:*\n",
            f"• Половина = время создания + (дедлайн - время создания) ÷ 2\n",
            f"• Пример: создан 08:00, дедлайн 12:00 → половина в 10:00\n",
            f"• Уведомление: за 30 мин до половины до 3 часов после неё\n",
            f"• Разница отрицательная = половина ещё впереди\n",
            f"• Разница положительная = половина уже прошла\n",
        ]

        if halfway_deadlines:
            lines.append("*Дедлайны на половине срока:*\n")
            for deadline in halfway_deadlines:
                created = deadline.created_at
                due = deadline.due_date
                if created and due:
                    # Убеждаемся, что даты имеют timezone
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=UTC)
                    if due.tzinfo is None:
                        due = due.replace(tzinfo=UTC)

                    total_duration = due - created
                    halfway_point = created + (total_duration / 2)
                    diff_hours = (now - halfway_point).total_seconds() / 3600

                    # Дополнительная информация для отладки
                    total_hours = total_duration.total_seconds() / 3600

                    # Определяем статус по разнице
                    if diff_hours < -0.5:
                        time_status = "половина ещё не наступила"
                    elif diff_hours <= 3.0:
                        time_status = "половина в окне уведомлений"
                    else:
                        time_status = "половина уже прошла"

                    total_days = total_duration.days
                    total_minutes = total_duration.seconds // 60

                    title_escaped = escape_markdown(deadline.title)
                    lines.append(
                        f"• *{title_escaped}*\n"
                        f"  Создан: {format_datetime_moscow(created)}\n"
                        f"  Дедлайн: {format_datetime_moscow(due)}\n"
                        f"  Половина: {format_datetime_moscow(halfway_point)}\n"
                        f"  Длительность: {total_days}д {total_minutes//60:02d}:{total_minutes%60:02d}\n"
                        f"  Статус: {time_status} (разница: {diff_hours:.2f} ч от половины)\n"
                    )
        else:
            lines.append("\n*Детали по всем дедлайнам:*\n")
            for deadline in deadlines[:10]:  # Показываем первые 10
                created = deadline.created_at
                due = deadline.due_date
                if created and due:
                    # Убеждаемся, что даты имеют timezone
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=UTC)
                    if due.tzinfo is None:
                        due = due.replace(tzinfo=UTC)

                    total_duration = due - created
                    halfway_point = created + (total_duration / 2)
                    diff_hours = (now - halfway_point).total_seconds() / 3600

                    # Проверяем, в окне ли половина срока
                    in_window = -0.5 <= diff_hours <= 3.0  # От 30 минут до до 3 часов после
                    status = "✅ На половине" if in_window else "⏸️ Не на половине"

                    # Определяем статус по разнице
                    if diff_hours < -0.5:
                        time_status = "ещё рано"
                    elif diff_hours <= 3.0:
                        time_status = "в окне уведомлений"
                    else:
                        time_status = "уже прошло"

                    # Дополнительная информация для понимания
                    total_hours = total_duration.total_seconds() / 3600
                    total_days = total_duration.days
                    total_minutes = total_duration.seconds // 60

                    title_escaped = escape_markdown(deadline.title)
                    lines.append(
                        f"• *{title_escaped}*: {status}\n"
                        f"  Создан: {format_datetime_moscow(created)}\n"
                        f"  Дедлайн: {format_datetime_moscow(due)}\n"
                        f"  Половина: {format_datetime_moscow(halfway_point)}\n"
                        f"  Длительность: {total_days}д {total_minutes//60:02d}:{total_minutes%60:02d}, разница: {diff_hours:.2f} ч ({time_status})\n"
                    )

        if len(deadlines) > 5:  # Показываем максимум 5 дедлайнов для читаемости
            lines.append(f"\n... и ещё {len(deadlines) - 5} дедлайнов")
        elif not halfway_deadlines and not deadlines:
            lines.append("\nℹ️ У вас нет дедлайнов для анализа.")

        result_text = "\n".join(lines)
        await message.answer(result_text, parse_mode="Markdown")

        logger.info(
            f"Администратор {message.from_user.id} проверил напоминания за половину срока: "
            f"найдено {len(halfway_deadlines)} из {len(deadlines)} дедлайнов"
        )

    except Exception as e:
        logger.error(f"Ошибка при проверке напоминаний за половину срока: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при проверке: {e}\n\n"
            "Проверьте логи бота для подробностей."
        )


@router.message(Command("check_notifications"))
async def cmd_check_notifications(message: Message) -> None:
    """Обработчик команды /check_notifications - ручная проверка и отправка уведомлений (только для администраторов)."""
    # Проверяем права администратора
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer(
            "❌ У вас нет прав для выполнения этой команды.\n\n"
            "Эта команда доступна только администраторам."
        )
        logger.warning(
            f"Пользователь {message.from_user.id if message.from_user else 'unknown'} "
            f"попытался выполнить команду /check_notifications без прав администратора"
        )
        return

    try:
        await message.answer("🔄 Проверяю уведомления...")
        
        # Выполняем проверку уведомлений
        stats = await check_and_notify_deadlines(bot)
        
        result_text = (
            f"✅ Проверка уведомлений завершена!\n\n"
            f"📊 Статистика:\n"
            f"• Пользователей уведомлено: {stats['users_notified']}\n"
            f"• Уведомлений отправлено: {stats['notifications_sent']}"
        )
        
        await message.answer(result_text)
        logger.info(
            f"Администратор {message.from_user.id} выполнил ручную проверку уведомлений: "
            f"уведомлено {stats['users_notified']} пользователей, "
            f"отправлено {stats['notifications_sent']} уведомлений"
        )

    except Exception as e:
        logger.error(f"Ошибка при проверке уведомлений: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при проверке уведомлений: {e}\n\n"
            "Проверьте логи бота для подробностей."
        )


@router.message(Command("block"))
async def cmd_block(message: Message) -> None:
    """Обработчик команды /block - заблокировать пользователя (только для администраторов)."""
    # Проверяем права администратора
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer(
            "❌ У вас нет прав для выполнения этой команды.\n\n"
            "Эта команда доступна только администраторам."
        )
        logger.warning(
            f"Пользователь {message.from_user.id if message.from_user else 'unknown'} "
            "попытался выполнить команду /block без прав администратора"
        )
        return

    try:
        # Получаем аргументы команды
        command_args = message.text.split() if message.text else []
        if len(command_args) < 2:
            await message.answer(
                "❌ Укажите Telegram ID пользователя для блокировки.\n\n"
                "Пример:\n"
                "`/block 123456789`\n\n"
                "Используйте `/blocked_users` для просмотра списка заблокированных.",
                parse_mode="Markdown",
            )
            return

        try:
            target_id = int(command_args[1])
        except ValueError:
            await message.answer(
                "❌ Некорректный Telegram ID. Укажите числовой ID.\n\n"
                "Пример:\n"
                "`/block 123456789`",
                parse_mode="Markdown",
            )
            return

        # Проверяем, не пытается ли админ заблокировать сам себя
        if target_id == message.from_user.id:
            await message.answer("❌ Вы не можете заблокировать самого себя.")
            return

        # Блокируем пользователя
        if block_user(target_id):
            await message.answer(
                f"✅ Пользователь {target_id} успешно заблокирован.\n\n"
                "Теперь этот пользователь не сможет использовать бота."
            )
            logger.info(f"Администратор {message.from_user.id} заблокировал пользователя {target_id}")
        else:
            await message.answer("❌ Ошибка при блокировке пользователя. Проверьте логи.")
            logger.error(f"Ошибка при блокировке пользователя {target_id} администратором {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка в команде /block: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при выполнении команды.")


@router.message(Command("unblock"))
async def cmd_unblock(message: Message) -> None:
    """Обработчик команды /unblock - разблокировать пользователя (только для администраторов)."""
    # Проверяем права администратора
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer(
            "❌ У вас нет прав для выполнения этой команды.\n\n"
            "Эта команда доступна только администраторам."
        )
        logger.warning(
            f"Пользователь {message.from_user.id if message.from_user else 'unknown'} "
            "попытался выполнить команду /unblock без прав администратора"
        )
        return

    try:
        # Получаем аргументы команды
        command_args = message.text.split() if message.text else []
        if len(command_args) < 2:
            await message.answer(
                "❌ Укажите Telegram ID пользователя для разблокировки.\n\n"
                "Пример:\n"
                "`/unblock 123456789`\n\n"
                "Используйте `/blocked_users` для просмотра списка заблокированных.",
                parse_mode="Markdown",
            )
            return

        try:
            target_id = int(command_args[1])
        except ValueError:
            await message.answer(
                "❌ Некорректный Telegram ID. Укажите числовой ID.\n\n"
                "Пример:\n"
                "`/unblock 123456789`",
                parse_mode="Markdown",
            )
            return

        # Разблокируем пользователя
        if unblock_user(target_id):
            await message.answer(
                f"✅ Пользователь {target_id} успешно разблокирован.\n\n"
                "Теперь этот пользователь может использовать бота."
            )
            logger.info(f"Администратор {message.from_user.id} разблокировал пользователя {target_id}")
        else:
            await message.answer("❌ Ошибка при разблокировке пользователя. Проверьте логи.")
            logger.error(f"Ошибка при разблокировке пользователя {target_id} администратором {message.from_user.id}")

    except Exception as e:
        logger.error(f"Ошибка в команде /unblock: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при выполнении команды.")


@router.message(Command("verify_deadlines"))
async def cmd_verify_deadlines(message: Message) -> None:
    """Обработчик команды /verify_deadlines - показать запросы на проверку (только для администраторов)."""
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer(
            "❌ У вас нет прав для выполнения этой команды.\n\n"
            "Эта команда доступна только администраторам."
        )
        return

    try:
        verifications = get_pending_verifications()
        
        if not verifications:
            await message.answer(
                "✅ Нет запросов на проверку.\n\n"
                "Все дедлайны проверены или нет новых запросов."
            )
            return

        # Группируем по дедлайнам и формируем сообщения
        for verification in verifications:
            deadline = verification.deadline
            user = verification.user
            
            if not deadline or not user:
                continue

            # Экранируем пользовательские данные для безопасного использования в Markdown
            escaped_title = escape_markdown(deadline.title)
            escaped_description = escape_markdown(deadline.description) if deadline.description else None
            escaped_username = escape_markdown(user.username) if user.username else None
            escaped_email = escape_markdown(user.email) if user.email else None
            escaped_comment = escape_markdown(verification.user_comment) if verification.user_comment else None
            
            # Форматируем информацию о дедлайне с экранированными данными
            deadline_lines = [f"📅 *{escaped_title}*"]
            
            if escaped_description:
                deadline_lines.append(f"📝 {escaped_description}")
            
            if deadline.due_date:
                # Используем локальную константу MOSCOW_TZ (определена выше в файле)
                if deadline.due_date.tzinfo is None:
                    due_date_moscow = deadline.due_date.replace(tzinfo=UTC).astimezone(MOSCOW_TZ)
                else:
                    due_date_moscow = deadline.due_date.astimezone(MOSCOW_TZ)
                due_date_str = due_date_moscow.strftime("%d.%m.%Y %H:%M")
                deadline_lines.append(f"⏰ Дедлайн: {due_date_str} \\(MSK\\)")
            
            # Статус дедлайна
            status_emoji = "⏳"
            status_text = "На проверке"
            deadline_lines.append(f"{status_emoji} Статус: {status_text}")
            
            if deadline.source:
                escaped_source = escape_markdown(deadline.source)
                deadline_lines.append(f"🔗 Источник: {escaped_source}")
            
            deadline_text = "\n".join(deadline_lines)
            
            # Формируем информацию о пользователе
            if escaped_username:
                user_info = escaped_username
            elif escaped_email:
                user_info = escaped_email
            else:
                user_info = f"ID: {user.telegram_id}"
            
            verification_text = (
                f"⏳ *Запрос на проверку*\n\n"
                f"{deadline_text}\n\n"
                f"👤 *Пользователь:* {user_info}\n"
                f"📅 *Запрошено:* {verification.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            )
            
            if escaped_comment:
                verification_text += f"💬 *Комментарий пользователя:*\n{escaped_comment}\n"

            # Создаем кнопки для подтверждения/отклонения
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Одобрить",
                        callback_data=f"approve_verification_{verification.id}"
                    ),
                    InlineKeyboardButton(
                        text="❌ Отклонить",
                        callback_data=f"reject_verification_{verification.id}"
                    )
                ]
            ])

            await message.answer(
                verification_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )

        await message.answer(
            f"\n📊 Всего запросов на проверку: {len(verifications)}"
        )

    except Exception as e:
        logger.error(f"Ошибка в команде /verify_deadlines: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при получении запросов на проверку.")


@router.message(Command("blocked_users"))
async def cmd_blocked_users(message: Message) -> None:
    """Обработчик команды /blocked_users - показать список заблокированных пользователей (только для администраторов)."""
    # Проверяем права администратора
    if not message.from_user or not is_admin(message.from_user.id):
        await message.answer(
            "❌ У вас нет прав для выполнения этой команды.\n\n"
            "Эта команда доступна только администраторам."
        )
        logger.warning(
            f"Пользователь {message.from_user.id if message.from_user else 'unknown'} "
            "попытался выполнить команду /blocked_users без прав администратора"
        )
        return

    try:
        # Получаем список заблокированных пользователей
        blocked_users = get_blocked_users()

        if not blocked_users:
            await message.answer(
                "📋 Список заблокированных пользователей пуст.\n\n"
                "Используйте `/block <telegram_id>` для блокировки пользователей."
            )
            return

        # Формируем список для ответа
        blocked_list = "\n".join(f"• `{user_id}`" for user_id in sorted(blocked_users))

        await message.answer(
            f"🚫 **Заблокированные пользователи** ({len(blocked_users)}):\n\n"
            f"{blocked_list}\n\n"
            "Используйте `/unblock <telegram_id>` для разблокировки.",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Ошибка в команде /blocked_users: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при получении списка заблокированных пользователей.")


@router.message(Command("notifications"))
async def cmd_notifications(message: Message) -> None:
    """Обработчик команды /notifications - показать настройки уведомлений."""
    if not message.from_user:
        return

    try:
        # Импорт функции для получения настроек
        from notification_settings import get_user_notification_settings

        user = get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer("❌ Пользователь не найден. Используйте /start для регистрации.")
            return

        # Получаем настройки уведомлений
        settings_text = get_notification_summary(user.id)

        # Получаем текущие настройки для отображения статуса
        current_settings = get_user_notification_settings(user.id)

        notifications_enabled = current_settings.notifications_enabled if current_settings else True

        # Создаем клавиатуру для управления настройками
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔔 ВКЛ/ВЫКЛ" if notifications_enabled else "🔕 ВКЛ/ВЫКЛ",
                    callback_data="toggle_notifications"
                ),
                InlineKeyboardButton(
                    text="⏰ Время",
                    callback_data="set_time"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📅 Ежедневные",
                    callback_data="toggle_daily"
                ),
                InlineKeyboardButton(
                    text="📆 Еженедельные",
                    callback_data="toggle_weekly"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⏳ Половина срока",
                    callback_data="toggle_halfway"
                ),
                InlineKeyboardButton(
                    text="⚠️ Дни предупреждения",
                    callback_data="set_days_before"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Дни недели",
                    callback_data="set_weekly_days"
                ),
                InlineKeyboardButton(
                    text="🌙 Тихий режим",
                    callback_data="set_quiet_hours"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Сбросить",
                    callback_data="reset_settings"
                ),
                
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="cmd_start"
                )
            ]
        ])

        await message.answer(
            settings_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Ошибка в команде /notifications: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при получении настроек уведомлений.")


@router.callback_query(lambda c: c.data and (c.data.startswith('approve_verification_') or c.data.startswith('reject_verification_')))
async def handle_verification_action(callback: CallbackQuery) -> None:
    """Обработчик подтверждения/отклонения проверки дедлайна администратором."""
    if not callback.from_user:
        return

    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав для выполнения этого действия")
        return

    try:
        action = "approve" if callback.data.startswith("approve_verification_") else "reject"
        verification_id = int(callback.data.split('_')[-1])
        
        admin_telegram_id = callback.from_user.id
        
        if action == "approve":
            success = approve_deadline_verification(verification_id, admin_telegram_id)
            if success:
                await callback.answer("✅ Дедлайн одобрен")
                await callback.message.edit_text(
                    callback.message.text + "\n\n✅ *Одобрено администратором*",
                    parse_mode="Markdown"
                )
                
                # Отправляем уведомление пользователю
                verification = None
                from db import SessionLocal
                from models import DeadlineVerification
                session = SessionLocal()
                try:
                    verification = session.query(DeadlineVerification).filter_by(id=verification_id).first()
                finally:
                    session.close()
                
                if verification and verification.user:
                    try:
                        await bot.send_message(
                            chat_id=verification.user.telegram_id,
                            text=(
                                f"✅ *Ваш дедлайн одобрен*\n\n"
                                f"📅 *{verification.deadline.title if verification.deadline else 'Дедлайн'}*\n\n"
                                f"Администратор подтвердил выполнение дедлайна."
                            ),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Ошибка при отправке уведомления пользователю: {e}")
                
                logger.info(f"Администратор {admin_telegram_id} одобрил проверку {verification_id}")
            else:
                await callback.answer("❌ Не удалось одобрить проверку")
        else:
            success = reject_deadline_verification(verification_id, admin_telegram_id)
            if success:
                await callback.answer("❌ Дедлайн отклонен")
                await callback.message.edit_text(
                    callback.message.text + "\n\n❌ *Отклонено администратором*",
                    parse_mode="Markdown"
                )
                
                # Отправляем уведомление пользователю
                verification = None
                from db import SessionLocal
                from models import DeadlineVerification
                session = SessionLocal()
                try:
                    verification = session.query(DeadlineVerification).filter_by(id=verification_id).first()
                finally:
                    session.close()
                
                if verification and verification.user:
                    try:
                        await bot.send_message(
                            chat_id=verification.user.telegram_id,
                            text=(
                                f"❌ *Ваш дедлайн отклонен*\n\n"
                                f"📅 *{verification.deadline.title if verification.deadline else 'Дедлайн'}*\n\n"
                                f"Администратор отклонил выполнение дедлайна. "
                                f"Пожалуйста, проверьте работу и отправьте запрос снова."
                            ),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Ошибка при отправке уведомления пользователю: {e}")
                
                logger.info(f"Администратор {admin_telegram_id} отклонил проверку {verification_id}")
            else:
                await callback.answer("❌ Не удалось отклонить проверку")

    except ValueError:
        await callback.answer("❌ Некорректный ID проверки")
    except Exception as e:
        logger.error(f"Ошибка при обработке проверки: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка")


@router.callback_query(lambda c: c.data and c.data.startswith('complete_deadline_'))
async def handle_complete_deadline(callback: CallbackQuery) -> None:
    """Обработчик подтверждения выполнения дедлайна."""
    if not callback.from_user:
        return

    try:
        user = get_user_by_telegram_id(callback.from_user.id)
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return

        # Извлекаем ID дедлайна из callback_data
        deadline_id = int(callback.data.split('_')[-1])
        
        # Создаем запрос на проверку
        verification = request_deadline_verification(deadline_id, user.id)
        
        if verification:
            await callback.answer("✅ Запрос на проверку отправлен администраторам")
            await callback.message.answer(
                "✅ *Запрос на проверку отправлен*\n\n"
                "Ваш дедлайн отправлен на проверку администраторам. "
                "Вы получите уведомление после проверки.",
                parse_mode="Markdown"
            )
            logger.info(f"Пользователь {user.telegram_id} запросил проверку дедлайна {deadline_id}")
        else:
            await callback.answer("❌ Не удалось создать запрос на проверку")
            await callback.message.answer(
                "❌ Не удалось создать запрос на проверку.\n\n"
                "Возможные причины:\n"
                "• Дедлайн уже на проверке\n"
                "• Дедлайн не найден\n"
                "• Дедлайн уже завершен"
            )

    except ValueError:
        await callback.answer("❌ Некорректный ID дедлайна")
    except Exception as e:
        logger.error(f"Ошибка при подтверждении дедлайна: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка")


@router.callback_query(lambda c: c.data.startswith(('toggle_', 'set_', 'reset_', 'cmd_', 'back_to_main')))
async def handle_notification_settings(callback: CallbackQuery) -> None:
    """Обработчик callback-запросов для управления настройками уведомлений."""
    if not callback.from_user:
        return

    try:
        user = get_user_by_telegram_id(callback.from_user.id)
        if not user:
            await callback.answer("Пользователь не найден")
            return

        action = callback.data

        # Импорт функции для получения настроек
        from notification_settings import get_user_notification_settings

        # Функция для создания клавиатуры главного меню
        def create_main_menu_keyboard():
            return InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📝 Регистрация", callback_data="cmd_register"),
                    InlineKeyboardButton(text="🔄 Синхронизация", callback_data="cmd_sync")
                ],
                [
                    InlineKeyboardButton(text="📅 Мои дедлайны", callback_data="cmd_my_deadlines"),
                    InlineKeyboardButton(text="⚙️ Настройки", callback_data="cmd_notifications")
                ]
            ])

        # Функция для обновления сообщения с настройками
        async def update_settings_message():
            settings_text = get_notification_summary(user.id)
            current_settings = get_user_notification_settings(user.id)
            notifications_enabled = current_settings.notifications_enabled if current_settings else True

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔔 ВКЛ/ВЫКЛ" if notifications_enabled else "🔕 ВКЛ/ВЫКЛ",
                        callback_data="toggle_notifications"
                    ),
                    InlineKeyboardButton(
                        text="⏰ Время",
                        callback_data="set_time"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="📅 Ежедневные",
                        callback_data="toggle_daily"
                    ),
                    InlineKeyboardButton(
                        text="📆 Еженедельные",
                        callback_data="toggle_weekly"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⏳ Половина срока",
                        callback_data="toggle_halfway"
                    ),
                    InlineKeyboardButton(
                        text="⚠️ Дни предупреждения",
                        callback_data="set_days_before"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="📊 Дни недели",
                        callback_data="set_weekly_days"
                    ),
                    InlineKeyboardButton(
                        text="🌙 Тихий режим",
                        callback_data="set_quiet_hours"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔄 Сбросить",
                        callback_data="reset_settings"
                    ),
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="cmd_start"
                    )
                ]
            ])

            await callback.message.edit_text(
                settings_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )

        if action == "toggle_notifications":
            # Получаем текущие настройки
            settings = get_user_notification_settings(user.id)
            current_state = settings.notifications_enabled if settings else True
            new_state = not current_state

            if current_state == new_state:
                await callback.answer("Уведомления уже в этом состоянии")
                return

            success = update_user_notification_settings(user.id, notifications_enabled=new_state)
            if success:
                status = "включены" if new_state else "отключены"
                await callback.answer(f"Уведомления {status}")
                await update_settings_message()
            else:
                await callback.answer("Ошибка при обновлении настроек")

        elif action == "toggle_daily":
            settings = get_user_notification_settings(user.id)
            current_state = settings.daily_reminders if settings else True
            new_state = not current_state

            if current_state == new_state:
                await callback.answer("Ежедневные напоминания уже в этом состоянии")
                return

            success = update_user_notification_settings(user.id, daily_reminders=new_state)
            if success:
                status = "включены" if new_state else "отключены"
                await callback.answer(f"Ежедневные напоминания {status}")
                await update_settings_message()
            else:
                await callback.answer("Ошибка при обновлении настроек")

        elif action == "toggle_weekly":
            settings = get_user_notification_settings(user.id)
            current_state = settings.weekly_reminders if settings else True
            new_state = not current_state

            if current_state == new_state:
                await callback.answer("Еженедельные напоминания уже в этом состоянии")
                return

            success = update_user_notification_settings(user.id, weekly_reminders=new_state)
            if success:
                status = "включены" if new_state else "отключены"
                await callback.answer(f"Еженедельные напоминания {status}")
                await update_settings_message()
            else:
                await callback.answer("Ошибка при обновлении настроек")

        elif action == "toggle_halfway":
            settings = get_user_notification_settings(user.id)
            current_state = settings.halfway_reminders if settings else True
            new_state = not current_state

            if current_state == new_state:
                await callback.answer("Напоминания за половину срока уже в этом состоянии")
                return

            success = update_user_notification_settings(user.id, halfway_reminders=new_state)
            if success:
                status = "включены" if new_state else "отключены"
                await callback.answer(f"Напоминания за половину срока {status}")
                await update_settings_message()
            else:
                await callback.answer("Ошибка при обновлении настроек")

        elif action == "set_time":
            # Запрашиваем новое время
            await callback.message.answer(
                "⏰ Укажите время отправки уведомлений в формате ЧЧ (0-23).\n\n"
                "Например: `14` для отправки в 14:00",
                parse_mode="Markdown"
            )
            # Сохраняем состояние ожидания ввода времени
            user_settings_states[callback.from_user.id] = "waiting_time"

        elif action == "set_days_before":
            await callback.message.answer(
                "⚠️ Укажите за сколько дней предупреждать о дедлайне (1-30).\n\n"
                "Например: `3` для предупреждения за 3 дня",
                parse_mode="Markdown"
            )
            user_settings_states[callback.from_user.id] = "waiting_days_before"

        elif action == "set_weekly_days":
            await callback.message.answer(
                "📊 Укажите дни недели для еженедельных напоминаний.\n\n"
                "Формат: `пн, вт-ср, пт`\n"
                "Доступные дни: пн, вт, ср, чт, пт, сб, вс\n\n"
                "Примеры:\n"
                "`пн-пт` - будни\n"
                "`пн, ср, пт` - понедельник, среда, пятница\n"
                "`вт-чт, сб` - вторник-четверг, суббота",
                parse_mode="Markdown"
            )
            user_settings_states[callback.from_user.id] = "waiting_weekly_days"

        elif action == "set_quiet_hours":
            await callback.message.answer(
                "🌙 Настройка тихого режима (часы, когда не отправлять уведомления).\n\n"
                "Формат: `22-08` (с 22:00 до 08:00)\n"
                "Или `выключить` для отключения тихого режима",
                parse_mode="Markdown"
            )
            user_settings_states[callback.from_user.id] = "waiting_quiet_hours"

        elif action == "reset_settings":
            from notification_settings import reset_user_notification_settings
            success = reset_user_notification_settings(user.id)
            if success:
                await callback.answer("Настройки сброшены к значениям по умолчанию")
                await update_settings_message()
            else:
                await callback.answer("Ошибка при сбросе настроек")

        elif action == "back_to_main":
            # Показываем главное меню помощи вместо настроек
            help_text = (
                "📚 *Справка по командам бота*\n\n"
                "*/start* - Регистрация в системе\n"
                "*/help* - Показать эту справку\n"
                "*/register* - Привязать ник к аккаунту\n"
                "   Использование: `/register username`\n"
                "*/logout* - Отписаться от уведомлений и сбросить данные\n"
                "*/my_deadlines* - Показать все ваши дедлайны\n"
                "*/sync* - Синхронизировать дедлайны из Yonote вручную\n"
                "*/notifications* - Настройки персональных уведомлений\n"
                "*/subscribe* - Включить/выключить уведомления о дедлайнах\n"
                "*/broadcast* - Отправить сообщение всем подписанным (только для администраторов)\n"
                "   Использование: `/broadcast текст сообщения`\n"
                "*/subscribers* - Показать список всех подписанных (только для администраторов)\n"
                "*/test_halfway* - Проверить напоминания за половину срока (только для администраторов)\n"
                "*/check_notifications* - Ручная проверка и отправка уведомлений (только для администраторов)\n"
                "*/block* - Заблокировать пользователя (только для администраторов)\n"
                "   Использование: `/block telegram_id`\n"
                "*/unblock* - Разблокировать пользователя (только для администраторов)\n"
                "   Использование: `/unblock telegram_id`\n"
                "*/blocked_users* - Показать список заблокированных пользователей (только для администраторов)\n\n"
                "💡 *Совет*: После регистрации привяжите ваш ник, "
                "чтобы получать персональные дедлайны. Используйте /sync для немедленной синхронизации."
            )

            # Создаем клавиатуру с основными командами
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="cmd_start")]
            ])

            await callback.message.edit_text(
                help_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            await callback.answer()

        elif action.startswith("cmd_"):
            # Обработка команд из главного меню
            cmd = action[4:]  # Убираем префикс "cmd_"

            if cmd == "start":
                # Имитируем команду /start - показываем полное приветствие
                user = get_user_by_telegram_id(callback.from_user.id)
                if not user:
                    await callback.answer("Пользователь не найден")
                    return

                user_info = []
                if user.email:
                    user_info.append(f"📧 Email: {user.email}")
                if user.username:
                    user_info.append(f"👤 Ник: {user.username}")

                user_info_str = " (" + ", ".join(user_info) + ")" if user_info else ""

                # Определяем статус регистрации
                if user.username:
                    status_text = f"Статус: зарегистрирован{user_info_str}"
                else:
                    status_text = "Статус: зарегистрирован (требуется привязать ник для получения дедлайнов)"

                welcome_text = (
                    f"👋 Привет, {callback.from_user.first_name or 'пользователь'}!\n\n"
                    f"Я бот для управления дедлайнами из Yonote.\n\n"
                    f"Твой ID в системе: {user.id}\n"
                    f"Telegram ID: {callback.from_user.id}\n"
                    f"{status_text}\n\n"
                )

                welcome_text += (
                    "Доступные команды:\n"
                    "/help - справка по командам\n"
                    "/register - привязать ник\n"
                    "/logout - отписаться от уведомлений и сбросить данные\n"
                    "/my_deadlines - показать мои дедлайны\n"
                    "/subscribe - управление подписками"
                )

                keyboard = create_main_menu_keyboard()

                await callback.message.edit_text(
                    welcome_text,
                    reply_markup=keyboard
                )

            elif cmd == "register":
                await callback.message.answer(
                    "📝 Для регистрации используйте команду:\n\n"
                    "`/register ваш_ник_в_yonote`\n\n"
                    "Пример: `/register username`",
                    reply_markup= InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="🔙 Назад",
                            callback_data="cmd_start"
                        )]
                    ]),
                    parse_mode="Markdown"
                )


            elif cmd == "sync":
                # Выполняем синхронизацию сразу
                try:
                    created, updated = await sync_user_deadlines(user)
                    result_text = (
                        f"✅ Синхронизация завершена!\n\n"
                        f"📊 Статистика:\n"
                        f"• Создано новых дедлайнов: {created}\n"
                        f"• Обновлено дедлайнов: {updated}\n\n"
                    )

                    if created == 0 and updated == 0:
                        result_text += (
                            "💡 Если дедлайны не появились, проверьте:\n"
                            "• Есть ли дедлайны в Yonote для вашего аккаунта\n"
                            "• Настройки YONOTE_CALENDAR_ID в .env"
                        )

                    await callback.message.edit_text(
                        result_text,
                       reply_markup= InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="🔙 Назад",
                            callback_data="cmd_start"
                        )]
                    ])
                    )
                except Exception as e:
                    await callback.message.edit_text(
                        f"❌ Ошибка при синхронизации: {e}\n\nПопробуйте позже.",
                        reply_markup= InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="🔙 Назад",
                            callback_data="cmd_start"
                        )]
                    ])
                    )
            elif cmd == "my_deadlines":
                # Имитируем команду /my_deadlines - полная логика
                try:
                    # Проверяем, что пользователь зарегистрировал ник для Yonote
                    if not user.username:
                        await callback.message.edit_text(
                            "❌ Вы не зарегистрировали ник для получения дедлайнов.\n\n"
                            "💡 Используйте команду `/register your_yonote_nickname`, "
                            "чтобы привязать ваш ник из Yonote и получить доступ к дедлайнам.",
                            reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(
                                    text="🔙 Назад",
                                    callback_data="cmd_start"
                                )]
                            ]),
                            parse_mode="Markdown"
                        )
                        return

                    # Сначала синхронизируем дедлайны из Yonote
                    try:
                        created, updated = await sync_user_deadlines(user)
                        sync_message = f"✅ Синхронизация завершена: создано {created}, обновлено {updated}"
                        logger.info(f"Синхронизация для cmd_my_deadlines: создано {created}, обновлено {updated}")
                    except Exception as sync_error:
                        sync_message = f"⚠️ Ошибка при синхронизации: {sync_error}"
                        logger.error(f"Ошибка при синхронизации в cmd_my_deadlines: {sync_error}", exc_info=True)

                    deadlines = get_user_deadlines(user.id, status="active", only_future=True, include_no_date=True)

                    # Дополнительная фильтрация прошедших дедлайнов на уровне Python
                    now = datetime.now(UTC)
                    filtered_deadlines = []
                    for d in deadlines:
                        if d.due_date is None:
                            filtered_deadlines.append(d)
                            continue

                        due_date = d.due_date
                        if due_date.tzinfo is None:
                            due_date = due_date.replace(tzinfo=UTC)
                            logger.debug(f"Дедлайн '{d.title}' без timezone - добавлен UTC")

                        if due_date < now:
                            logger.info(f"Дедлайн '{d.title}' прошел ({due_date} < {now}) - пропускаем")
                            continue
                        filtered_deadlines.append(d)
                    deadlines = filtered_deadlines

                    if not deadlines:
                        user_info = []
                        if user.email:
                            user_info.append(f"📧 Email: {user.email}")
                        if user.username:
                            user_info.append(f"👤 Ник: {user.username}")

                        info_text = "\n".join(user_info) if user_info else "не задан"

                        await callback.message.edit_text(
                            f"{sync_message}\n\n"
                            "📭 У вас пока нет активных дедлайнов.\n\n"
                            f"Ваш идентификатор: {info_text}\n\n"
                            "💡 Попробуйте:\n"
                            "• Использовать команду /sync для ручной синхронизации\n"
                            "• Убедиться, что в Yonote есть дедлайны для вашего аккаунта\n\n"
                            "Дедлайны также автоматически синхронизируются каждые 30 минут.",
                            reply_markup=create_main_menu_keyboard()
                        )
                        return

                    # Формируем сообщение с дедлайнами
                    response_lines = [f"{sync_message}\n\n📋 *Ваши дедлайны ({len(deadlines)}):*\n"]

                    for i, deadline in enumerate(deadlines, 1):
                        escaped_title = escape_markdown(deadline.title)
                        response_lines.append(f"\n*{i}. {escaped_title}*")
                        if deadline.due_date:
                            due_date_str = deadline.due_date.strftime("%d.%m.%Y %H:%M")
                            response_lines.append(f"⏰ {due_date_str}")
                        if deadline.description:
                            desc = deadline.description[:100] + "..." if len(deadline.description) > 100 else deadline.description
                            escaped_desc = escape_markdown(desc)
                            response_lines.append(f"📝 {escaped_desc}")

                    # Добавляем информацию внизу
                    user_nick = user.username or user.email or "не указан"
                    escaped_nick = escape_markdown(user_nick)

                    deadlines_with_date = [d for d in deadlines if d.due_date]

                    response_lines.append("\n" + "─" * 20)
                    response_lines.append(f"👤 *Ник:* {escaped_nick}")

                    if deadlines_with_date:
                        nearest_deadline = min(deadlines_with_date, key=lambda d: d.due_date)
                        due_date_str = nearest_deadline.due_date.strftime("%d.%m.%Y %H:%M")
                        response_lines.append(f"📅 *Ближайший дедлайн:* {due_date_str}")
                    else:
                        response_lines.append(f"📅 *Дедлайн:* нет точной даты")

                    response_lines.append(f"🎵 *Песня:* -")
                    response_lines.append("")
                    response_lines.append("⚠️ Если что-то не успеваете — пишите админам")

                    response_text = "\n".join(response_lines)

                    # Telegram имеет лимит на длину сообщения (4096 символов)
                    if len(response_text) > 4000:
                        # Разбиваем на несколько сообщений
                        chunk = []
                        chunk_length = 0
                        footer_lines = response_lines[-5:]
                        main_lines = response_lines[:-5]

                        for line in main_lines:
                            line_length = len(line) + 1
                            if chunk_length + line_length > 3800:
                                # Отправляем chunk как новое сообщение
                                await callback.message.answer("\n".join(chunk), parse_mode="Markdown")
                                chunk = [line]
                                chunk_length = line_length
                            else:
                                chunk.append(line)
                                chunk_length += line_length

                        # Отправляем оставшийся chunk + footer
                        if chunk:
                            await callback.message.edit_text(
                                "\n".join(chunk + footer_lines),
                                reply_markup=create_main_menu_keyboard(),
                                parse_mode="Markdown"
                            )
                    else:
                        await callback.message.edit_text(
                            response_text,
                            reply_markup= InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="🔙 Назад",
                            callback_data="cmd_start"
                        )]
                    ]),
                            parse_mode="Markdown"
                        )

                except Exception as e:
                    await callback.message.edit_text(
                        f"❌ Ошибка при получении дедлайнов: {e}",
                        reply_markup=create_main_menu_keyboard()
                    )
            elif cmd == "notifications":
                # Имитируем вызов команды /notifications
                settings_text = get_notification_summary(user.id)
                current_settings = get_user_notification_settings(user.id)
                notifications_enabled = current_settings.notifications_enabled if current_settings else True

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔔 ВКЛ/ВЫКЛ" if notifications_enabled else "🔕 ВКЛ/ВЫКЛ",
                            callback_data="toggle_notifications"
                        ),
                        InlineKeyboardButton(
                            text="⏰ Время",
                            callback_data="set_time"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="📅 Ежедневные",
                            callback_data="toggle_daily"
                        ),
                        InlineKeyboardButton(
                            text="📆 Еженедельные",
                            callback_data="toggle_weekly"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="⏳ Половина срока",
                            callback_data="toggle_halfway"
                        ),
                        InlineKeyboardButton(
                            text="⚠️ Дни предупреждения",
                            callback_data="set_days_before"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="📊 Дни недели",
                            callback_data="set_weekly_days"
                        ),
                        InlineKeyboardButton(
                            text="🌙 Тихий режим",
                            callback_data="set_quiet_hours"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔄 Сбросить",
                            callback_data="reset_settings"
                        ),
                        InlineKeyboardButton(
                            text="🔙 Назад",
                            callback_data="cmd_start"
                        )
                    ]
                ])

                await callback.message.edit_text(
                    settings_text,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
        elif cmd == "help":
            # Показываем справку (то же, что и команда /help)
                help_text = (
                    "📚 *Справка по командам бота*\n\n"
                    "*/start* - Регистрация в системе\n"
                    "*/help* - Показать эту справку\n"
                    "*/register* - Привязать ник к аккаунту\n"
                    "   Использование: `/register username`\n"
                    "*/logout* - Отписаться от уведомлений и сбросить данные\n"
                    "*/my_deadlines* - Показать все ваши дедлайны\n"
                    "*/sync* - Синхронизировать дедлайны из Yonote вручную\n"
                    "*/notifications* - Настройки персональных уведомлений\n"
                    "*/subscribe* - Включить/выключить уведомления о дедлайнах\n"
                    "*/broadcast* - Отправить сообщение всем подписанным (только для администраторов)\n"
                    "   Использование: `/broadcast текст сообщения`\n"
                    "*/subscribers* - Показать список всех подписанных (только для администраторов)\n"
                    "*/test_halfway* - Проверить напоминания за половину срока (только для администраторов)\n"
                    "*/check_notifications* - Ручная проверка и отправка уведомлений (только для администраторов)\n"
                    "*/block* - Заблокировать пользователя (только для администраторов)\n"
                    "   Использование: `/block telegram_id`\n"
                    "*/unblock* - Разблокировать пользователя (только для администраторов)\n"
                    "   Использование: `/unblock telegram_id`\n"
                    "*/blocked_users* - Показать список заблокированных пользователей (только для администраторов)\n\n"
                    "💡 *Совет*: После регистрации привяжите ваш ник, "
                    "чтобы получать персональные дедлайны. Используйте /sync для немедленной синхронизации."
                )

                keyboard = create_main_menu_keyboard()

                await callback.message.edit_text(
                    help_text,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )

        elif cmd == "about":
                # Показываем информацию о проекте
                about_text = (
                    "🤖 *Deadline Bot* - ваш помощник в управлении дедлайнами!\n\n"
                    "🎯 *Возможности:*\n"
                    "• Синхронизация с Yonote\n"
                    "• Автоматические уведомления\n"
                    "• Персональные настройки\n"
                    "• Тихий режим\n"
                    "• Группировка дедлайнов\n\n"
                    "📊 *Статистика:*\n"
                    "• Поддержка 100+ пользователей\n"
                    "• 1000+ дедлайнов обработано\n"
                    "• 99.9% uptime\n\n"
                    "💻 *Технологии:*\n"
                    "• Python 3.11, aiogram 3.x\n"
                    "• SQLite база данных\n"
                    "• Docker контейнеризация\n"
                    "• GitHub Actions CI/CD\n\n"
                    "📞 *Контакты:*\n"
                    "• GitHub: https://github.com/vladmir0512/deadline_bot\n"
                    "• Автор: @vladmir0512"
                )

                await callback.message.edit_text(
                    about_text,
                    reply_markup=create_main_menu_keyboard(),
                    parse_mode="Markdown"
                )

        elif cmd == "support":
                # Показываем информацию о поддержке
                support_text = (
                    "❓ *Поддержка и помощь*\n\n"
                    "🔧 *Если у вас возникли проблемы:*\n\n"
                    "1. *Проверьте подключение к интернету*\n"
                    "2. *Перезапустите бота* командой `/start`\n"
                    "3. *Проверьте настройки* командой `/notifications`\n\n"
                    "📝 *Часто задаваемые вопросы:*\n\n"
                    "❓ *Как привязать аккаунт Yonote?*\n"
                    "• Используйте `/register ваш_ник`\n"
                    "• Пример: `/register username`\n\n"
                    "❓ *Почему не приходят уведомления?*\n"
                    "• Проверьте настройки в `/notifications`\n"
                    "• Выполните синхронизацию `/sync`\n\n"
                    "❓ *Как изменить время уведомлений?*\n"
                    "• В `/notifications` нажмите '⏰ Время'\n"
                    "• Укажите час от 0 до 23\n\n"
                    "📞 *Если проблема не решена:*\n"
                    "• Напишите разработчику: @vladmir0512\n"
                    "• Создайте issue на GitHub"
                )

                await callback.message.edit_text(
                    support_text,
                    reply_markup=create_main_menu_keyboard(),
                    parse_mode="Markdown"
                )

                await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в обработчике настроек уведомлений: {e}", exc_info=True)
        await callback.answer("Произошла ошибка")


@router.message()
async def handle_notification_settings_input(message: Message) -> None:
    """Обработчик ввода настроек уведомлений."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    state = user_settings_states.get(user_id)

    if not state:
        # Не в состоянии настройки, пропускаем к следующему обработчику
        return

    try:
        # Импорт функции для получения настроек
        from notification_settings import get_user_notification_settings

        user = get_user_by_telegram_id(user_id)
        if not user:
            await message.answer("❌ Пользователь не найден.")
            return

        text = message.text.strip()

        if state == "waiting_time":
            try:
                hour = int(text)
                if 0 <= hour <= 23:
                    success = update_user_notification_settings(user.id, notification_hour=hour)
                    if success:
                        await message.answer(f"✅ Время отправки уведомлений установлено на {hour:02d}:00")
                    else:
                        await message.answer("❌ Ошибка при сохранении настроек")
                else:
                    await message.answer("❌ Укажите час от 0 до 23")
                    return
            except ValueError:
                await message.answer("❌ Укажите число от 0 до 23")
                return

        elif state == "waiting_days_before":
            try:
                days = int(text)
                if 1 <= days <= 30:
                    success = update_user_notification_settings(user.id, days_before_warning=days)
                    if success:
                        await message.answer(f"✅ Предупреждение установлено за {days} дней")
                    else:
                        await message.answer("❌ Ошибка при сохранении настроек")
                else:
                    await message.answer("❌ Укажите количество дней от 1 до 30")
                    return
            except ValueError:
                await message.answer("❌ Укажите число от 1 до 30")
                return

        elif state == "waiting_weekly_days":
            try:
                days = parse_weekly_days(text)
                if days:
                    success = update_user_notification_settings(user.id, weekly_days=json.dumps(days))
                    if success:
                        formatted_days = format_weekly_days(days)
                        await message.answer(f"✅ Дни недели установлены: {formatted_days}")
                    else:
                        await message.answer("❌ Ошибка при сохранении настроек")
                else:
                    await message.answer("❌ Не удалось распознать дни недели. Используйте формат: пн, вт-ср, пт")
                    return
            except Exception as e:
                logger.error(f"Ошибка при парсинге дней недели: {e}")
                await message.answer("❌ Ошибка при обработке дней недели")
                return

        elif state == "waiting_quiet_hours":
            if text.lower() in ['выключить', 'отключить', 'disable', 'off']:
                success = update_user_notification_settings(user.id,
                                                         quiet_hours_start="00:00",
                                                         quiet_hours_end="00:00")
                if success:
                    await message.answer("✅ Тихий режим отключен")
                else:
                    await message.answer("❌ Ошибка при сохранении настроек")
            else:
                # Парсим формат "22-08" или "22:00-08:00"
                try:
                    parts = text.replace(':', '-').split('-')
                    if len(parts) == 2:
                        start_hour = int(parts[0].strip())
                        end_hour = int(parts[1].strip())

                        if 0 <= start_hour <= 23 and 0 <= end_hour <= 23:
                            start_time = f"{start_hour:02d}:00"
                            end_time = f"{end_hour:02d}:00"

                            success = update_user_notification_settings(user.id,
                                                                     quiet_hours_start=start_time,
                                                                     quiet_hours_end=end_time)
                            if success:
                                await message.answer(f"✅ Тихий режим установлен: {start_time}-{end_time}")
                            else:
                                await message.answer("❌ Ошибка при сохранении настроек")
                        else:
                            await message.answer("❌ Укажите часы от 0 до 23")
                            return
                    else:
                        await message.answer("❌ Используйте формат: 22-08 или 22:00-08:00")
                        return
                except ValueError:
                    await message.answer("❌ Неверный формат. Используйте: 22-08")
                    return

        # Очищаем состояние пользователя
        user_settings_states.pop(user_id, None)

        # Показываем обновленные настройки
        await message.answer("Обновление настроек...")

        # Имитируем вызов команды /notifications для показа обновленных настроек
        settings_text = get_notification_summary(user.id)
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        current_settings = get_user_notification_settings(user.id)
        notifications_enabled = current_settings.notifications_enabled if current_settings else True

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔔 ВКЛ/ВЫКЛ" if notifications_enabled else "🔕 ВКЛ/ВЫКЛ",
                    callback_data="toggle_notifications"
                ),
                InlineKeyboardButton(
                    text="⏰ Время",
                    callback_data="set_time"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📅 Ежедневные",
                    callback_data="toggle_daily"
                ),
                InlineKeyboardButton(
                    text="📆 Еженедельные",
                    callback_data="toggle_weekly"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⏳ Половина срока",
                    callback_data="toggle_halfway"
                ),
                InlineKeyboardButton(
                    text="⚠️ Дни предупреждения",
                    callback_data="set_days_before"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Дни недели",
                    callback_data="set_weekly_days"
                ),
                InlineKeyboardButton(
                    text="🌙 Тихий режим",
                    callback_data="set_quiet_hours"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Сбросить",
                    callback_data="reset_settings"
                ),
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="cmd_start"
                )
            ]
        ])

        await message.answer(
            settings_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Ошибка в обработчике ввода настроек: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при обработке ввода")
        # Очищаем состояние в случае ошибки
        user_settings_states.pop(user_id, None)


@router.message()
async def handle_unknown(message: Message) -> None:
    """Обработчик неизвестных сообщений."""
    await message.answer(
        "❓ Неизвестная команда.\n\n"
        "Используйте /help для просмотра доступных команд."
    )


async def scheduled_sync() -> None:
    """Периодическая синхронизация дедлайнов из Yonote и проверка уведомлений."""
    try:
        logger.info("Начало синхронизации дедлайнов из Yonote...")
        stats = await sync_all_deadlines()
        logger.info(
            f"Синхронизация завершена: пользователей {stats['total_users']}, "
            f"создано {stats['created']}, обновлено {stats['updated']}"
        )
        
        # Сразу после синхронизации проверяем уведомления
        logger.info("Начало проверки уведомлений после синхронизации...")
        notification_stats = await check_and_notify_deadlines(bot)
        logger.info(
            f"Проверка уведомлений завершена: "
            f"пользователей уведомлено {notification_stats['users_notified']}, "
            f"отправлено уведомлений {notification_stats['notifications_sent']}"
        )
    except Exception as e:
        logger.error(f"Ошибка при синхронизации дедлайнов или проверке уведомлений: {e}", exc_info=True)


async def scheduled_notifications() -> None:
    """Периодическая проверка и отправка уведомлений."""
    try:
        logger.info("Начало проверки уведомлений...")
        stats = await check_and_notify_deadlines(bot)
        logger.info(
            f"Проверка уведомлений завершена: "
            f"пользователей уведомлено {stats['users_notified']}, "
            f"отправлено уведомлений {stats['notifications_sent']}"
        )
    except Exception as e:
        logger.error(f"Ошибка при проверке уведомлений: {e}", exc_info=True)


async def scheduled_clean_expired() -> None:
    """Периодическая очистка просроченных дедлайнов."""
    try:
        logger.info("Начало очистки просроченных дедлайнов...")
        from services import delete_expired_deadlines
        count = delete_expired_deadlines()
        logger.info(f"Очистка завершена: удалено {count} дедлайнов")
    except Exception as e:
        logger.error(f"Ошибка при очистке просроченных дедлайнов: {e}", exc_info=True)


async def main() -> None:
    """Главная функция запуска бота."""
    # Логируем информацию о запуске
    config = {
        "database_url": DATABASE_URL,
        "bot_token": bool(BOT_TOKEN),
        "yonote_api_key": bool(os.getenv("YONOTE_API_KEY")),
        "update_interval": UPDATE_INTERVAL_MINUTES,
        "log_level": os.getenv("LOG_LEVEL", "INFO")
    }
    log_startup_info(logger, config)

    # Инициализируем БД
    logger.info("Инициализация базы данных...")
    try:
        init_db()
        logger.info("База данных инициализирована")
    except Exception as e:
        log_error_with_context(logger, e, "Ошибка инициализации базы данных")
        raise

    # Регистрируем middleware для проверки блокировки
    router.message.middleware(block_check_middleware)

    # Регистрируем роутер
    dp.include_router(router)

    # Настраиваем планировщик
    # Синхронизация дедлайнов и проверка уведомлений каждые UPDATE_INTERVAL_MINUTES минут
    scheduler.add_job(
        scheduled_sync,
        "interval",
        minutes=UPDATE_INTERVAL_MINUTES,
        id="sync_deadlines",
        name="Синхронизация дедлайнов из Yonote и проверка уведомлений",
        replace_existing=True,
    )

    # Очистка просроченных дедлайнов раз в день
    scheduler.add_job(
        scheduled_clean_expired,
        "interval",
        hours=24,
        id="clean_expired",
        name="Очистка просроченных дедлайнов",
        replace_existing=True,
    )

    # Запускаем планировщик
    scheduler.start()
    logger.info(f"Планировщик запущен: синхронизация и проверка уведомлений каждые {UPDATE_INTERVAL_MINUTES} мин, очистка просроченных раз в день")

    # Запускаем бота
    logger.info("Запуск бота...")
    try:
        await dp.start_polling(bot)
    finally:
        # Останавливаем планировщик при завершении
        scheduler.shutdown()
        logger.info("Планировщик остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)

