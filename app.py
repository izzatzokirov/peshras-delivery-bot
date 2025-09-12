from flask import Flask, request, jsonify
import requests
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# КОНФИГУРАЦИЯ
BOT_TOKEN = "8338994662:AAH7FALz3qd3F9dzcPadCVQY6CRPBXtFxiA"
CHANNEL_ID = "-1002967095913"

def send_to_telegram(order_data):
    try:
        # Формируем сообщение с артикулами
        message = f"🛒 Заказ #{order_data.get('order_num', 'N/A')}\n\n"
        
        # Добавляем товары с артикулами
        if 'line' in order_data and isinstance(order_data['line'], list):
            for i, item in enumerate(order_data['line'], 1):
                if item.get('order_line_type_id') == 1:  # Только товары
                    name = item.get('order_line_name', 'Товар')
                    quantity = item.get('order_line_quantity', 1)
                    art = item.get('order_line_art_number', 'без артикула')
                    price = item.get('order_line_sum', 0)
                    
                    message += f"{i}. {name} {quantity}шт. арт {art}\n"
        
        # Добавляем остальную информацию
        message += f"\n💰 Сумма: {order_data.get('order_sum', 0)} сомони\n"
        message += f"👤 Имя: {order_data.get('order_person', 'N/A')}\n"
        message += f"📞 Телефон: {order_data.get('order_phone', 'N/A')}\n"
        message += f"🏠 Адрес: {order_data.get('order_address', 'N/A')}\n"
        message += f"⏰ Время: {convert_unix_time(order_data.get('order_time', ''))}\n"
        message += f"💬 Комментарий: {order_data.get('order_comment', 'нет комментария')}\n"

        # Создаем кнопки
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Принять заказ", "callback_data": f"accept_{order_data.get('order_num')}"},
                    {"text": "🚗 В пути", "callback_data": f"delivery_{order_data.get('order_num')}"}
                ],
                [
                    {"text": "✅ Доставлен", "callback_data": f"delivered_{order_data.get('order_num')}"}
                ]
            ]
        }

        # Отправляем в Telegram
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHANNEL_ID,
            "text": message,
            "parse_mode": "HTML",
            "reply_markup": keyboard
        }
        
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки в Telegram: {e}")
        return False

def convert_unix_time(unix_time):
    try:
        return datetime.fromtimestamp(int(unix_time)).strftime('%Y-%m-%d %H:%M:%S')
    except:
        return unix_time

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        logger.info("📨 Получен заказ от storelend.ru")
        
        # Получаем данные
        order_data_str = request.form.get('order_data')
        if not order_data_str:
            return jsonify({"status": "error", "message": "No order_data"}), 400
        
        import json
        order_data = json.loads(order_data_str)
        
        # Отправляем в Telegram
        success = send_to_telegram(order_data)
        
        if success:
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error"}), 500
            
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return jsonify({"status": "error"}), 400

@app.route('/')
def home():
    return "Peshras Delivery Bot is running!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    # Добавьте эти импорты в начало файла
from threading import Thread
import time

# Глобальный словарь для отслеживания заказов
orders_status = {}

# Функция для обработки нажатий кнопок
def handle_callback_updates():
    """Отдельный поток для обработки нажатий кнопок"""
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if data["ok"] and data["result"]:
                for update in data["result"]:
                    if "callback_query" in update:
                        query = update["callback_query"]
                        message_id = query["message"]["message_id"]
                        callback_data = query["data"]
                        username = query["from"].get("username", query["from"]["first_name"])
                        
                        # Обрабатываем разные действия
                        if callback_data.startswith("accept_"):
                            order_num = callback_data.split("_")[1]
                            orders_status[order_num] = {"status": "принят", "courier": username}
                            
                            # Обновляем сообщение
                            new_text = query["message"]["text"] + f"\n\n✅ Принял: @{username}"
                            edit_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
                            payload = {
                                "chat_id": CHANNEL_ID,
                                "message_id": message_id,
                                "text": new_text,
                                "parse_mode": "HTML"
                            }
                            requests.post(edit_url, json=payload)
                            
                        elif callback_data.startswith("delivery_"):
                            order_num = callback_data.split("_")[1]
                            orders_status[order_num] = {"status": "в пути", "courier": username}
                            
                            new_text = query["message"]["text"] + f"\n\n🚗 В пути: @{username}"
                            edit_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
                            payload = {
                                "chat_id": CHANNEL_ID,
                                "message_id": message_id,
                                "text": new_text,
                                "parse_mode": "HTML"
                            }
                            requests.post(edit_url, json=payload)
                            
                        elif callback_data.startswith("delivered_"):
                            order_num = callback_data.split("_")[1]
                            orders_status[order_num] = {"status": "доставлен", "courier": username}
                            
                            new_text = query["message"]["text"] + f"\n\n✅ Доставлен: @{username}"
                            edit_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
                            payload = {
                                "chat_id": CHANNEL_ID,
                                "message_id": message_id,
                                "text": new_text,
                                "parse_mode": "HTML"
                            }
                            requests.post(edit_url, json=payload)
                        
                        # Подтверждаем обработку callback
                        answer_url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
                        requests.post(answer_url, json={"callback_query_id": query["id"]})
            
            time.sleep(1)  # Проверяем каждую секунду
            
        except Exception as e:
            logger.error(f"❌ Ошибка в обработке кнопок: {e}")
            time.sleep(5)

# Запускаем обработчик кнопок в отдельном потоке
callback_thread = Thread(target=handle_callback_updates, daemon=True)
callback_thread.start()

logger.info("✅ Обработчик кнопок запущен!")
