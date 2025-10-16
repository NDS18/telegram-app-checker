import telebot
import requests
import schedule
import time
import threading

# --- НАСТРОЙКИ ---
import os
BOT_TOKEN = os.environ.get('TELEGRAM_TOKEN') # Берем токен из окружения
CHECK_INTERVAL_MINUTES = 15  # Интервал проверки в минутах
# -----------------

bot = telebot.TeleBot(BOT_TOKEN)

# Словарь для хранения задач проверки для каждого пользователя
# Формат: {chat_id: {'url': 'ссылка', 'job': объект schedule}}
user_tasks = {}

def check_app_status(chat_id, app_url):
    """
    Проверяет статус приложения по URL.
    """
    try:
        response = requests.head(app_url, allow_redirects=True, timeout=10)
        # Если статус код 200, значит страница доступна
        if response.status_code == 200:
            message = f"✅ Приложение по ссылке {app_url} доступно."
        # Если 404, страница не найдена, возможно, приложение удалено
        elif response.status_code == 404:
            message = f"❗️ Приложение по ссылке {app_url} не найдено (Ошибка 404). Возможно, оно удалено или забанено."
        else:
            message = f"⚠️ Не удалось однозначно определить статус приложения по ссылке {app_url}. Статус-код: {response.status_code}."
    except requests.RequestException as e:
        message = f"❌ Не удалось проверить ссылку {app_url}. Ошибка: {e}"

    # Отправляем сообщение пользователю
    try:
        bot.send_message(chat_id, message)
    except Exception as e:
        print(f"Не удалось отправить сообщение пользователю {chat_id}: {e}")
        # Если не удалось отправить сообщение, возможно, пользователь заблокировал бота.
        # В таком случае, отменяем задачу для этого пользователя.
        if chat_id in user_tasks and user_tasks[chat_id]['job']:
            schedule.cancel_job(user_tasks[chat_id]['job'])
            del user_tasks[chat_id]
            print(f"Задача для пользователя {chat_id} отменена.")


@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Отправь мне ссылку на Android-приложение в Google Play, и я буду проверять его доступность каждые 15 минут.")

@bot.message_handler(commands=['stop'])
def stop_checking(message):
    chat_id = message.chat.id
    if chat_id in user_tasks:
        job = user_tasks[chat_id].get('job')
        if job:
            schedule.cancel_job(job)
        del user_tasks[chat_id]
        bot.reply_to(message, "Проверка остановлена.")
    else:
        bot.reply_to(message, "Активных проверок для вас не найдено.")


@bot.message_handler(func=lambda message: message.text.startswith('http'))
def start_checking(message):
    chat_id = message.chat.id
    app_url = message.text

    # Если для этого пользователя уже есть задача, отменяем ее
    if chat_id in user_tasks and user_tasks[chat_id].get('job'):
        schedule.cancel_job(user_tasks[chat_id]['job'])

    bot.reply_to(message, f"Принято! Начинаю проверку приложения по ссылке: {app_url}. Я буду сообщать о статусе каждые {CHECK_INTERVAL_MINUTES} минут.")

    # Сразу проверяем статус первый раз
    check_app_status(chat_id, app_url)

    # Создаем и сохраняем новую задачу
    job = schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(check_app_status, chat_id, app_url)
    user_tasks[chat_id] = {'url': app_url, 'job': job}

def run_scheduler():
    """
    Запускает бесконечный цикл для выполнения запланированных задач.
    """
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    # Запускаем планировщик в отдельном потоке
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.start()

    # Запускаем бота
    print("Бот запущен...")
    bot.polling(none_stop=True)
