from flask import Flask, request, jsonify
import requests
import logging
from datetime import datetime
from threading import Thread
import time

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# КОНФИГУРАЦИЯ
BOT_TOKEN = "8338994662:AAH7FALz3qd3F9dzcPadCVQY6CRPBXtFxiA"
CHANNEL_ID = "-1002967095913"

# Глобальный словарь для отслеживания заказов
orders_status = {}

def send_to_telegram(order_data):
    try:
        # Формируем сообщение
        message = f"🛒 Заказ #{order_data.get('order_num', 'N/A')}\n\n"
        
        # Добавляем товары с артикулами
        if 'line' in order_data and isinstance(order_data['line'], list):
            for i, item in enumerate(order_data['line'], 1):
                if item.get('order_line_type_id') == 1:  # Только товары
                    name = item.get('order_line_name', 'Товар')
                    quantity = item.get('order_line_quantity', 1)
                    art = item.get('order_line_art_number', 'без артикула')
                    message += f"{i}. {name} {quantity}шт. арт {art}\n"
        
        # Добавляем информацию об оплате
        payment_method = "Наличные"  # По умолчанию
        if order_data.get('payment_name'):
            payment_method = order_data.get('payment_name')
        
        message += f"\n💰 Сумма: {order_data.get('order_sum', 0)} сомони"
        message += f"\n💳 Оплата: {payment_method}"
        
        # Кликабельный телефон
        phone = order_data.get('order_phone', '')
        if phone:
            message += f"\n📞 Телефон: <a href=\"tel:{phone}\">{phone}</a>"
        
        # Остальная информация
        message += f"\n👤 Имя: {order_data.get('order_person', 'N/A')}"
        message += f"\n🏠 Адрес: {order_data.get('order_address', 'N/A')}"
        message += f"\n⏰ Время: {convert_unix_time(order_data.get('order_time', ''))}"
        
        comment = order_data.get('order_comment', '')
        if comment:
            message += f"\n💬 Комментарий: {comment}"

        # Создаем кнопки
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Принять заказ", "callback_data": f"accept_{order_data.get('order_num')}"},
                    {"text": "🚗 В пути", "callback_data": f"delivery_{order_data.get('order_num')}"}
                ],
                [
                    {"text": "✅ Доставлен", "callback_data": f"delivered_{order_data.get('order_num')}"},
                    {"text": "📞 Позвонить", "callback_data": f"call_{order_data.get('order_num')}"}
                ]
            ]
        }

        # Отправляем в Telegram
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHANNEL_ID,
            "text": message,
            "parse_mode": "HTML",
            "reply_markup": keyboard,
            "disable_web_page_preview": True
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

# Обработчик нажатий кнопок
def handle_callback_updates():
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=30"
            response = requests.get(url, timeout=35)
            data = response.json()
            
            if data["ok"] and data["result"]:
                for update in data["result"]:
                    if "callback_query" in update:
                        query = update["callback_query"]
                        callback_data = query["data"]
                        username = query["from"].get("username", query["from"]["first_name"])
                        order_num = callback_data.split("_")[1]
                        
                        # Обновляем сообщение
                        original_text = query["message"]["text"]
                        
                        if callback_data.startswith("accept_"):
                            new_text = original_text + f"\n\n✅ Принял: @{username}"
                        elif callback_data.startswith("delivery_"):
                            new_text = original_text + f"\n\n🚗 В пути: @{username}"
                        elif callback_data.startswith("delivered_"):
                            new_text = original_text + f"\n\n✅ Доставлен: @{username}"
                        elif callback_data.startswith("call_"):
                            # Для кнопки "Позвонить" просто отвечаем
                            answer_url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
                            requests.post(answer_url, json={"callback_query_id": query["id"], "text": "Нажмите на номер телефона выше ☝️"})
                            continue
                        
                        # Редактируем сообщение
                        edit_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
                        payload = {
                            "chat_id": CHANNEL_ID,
                            "message_id": query["message"]["message_id"],
                            "text": new_text,
                            "parse_mode": "HTML"
                        }
                        requests.post(edit_url, json=payload)
                        
                        # Подтверждаем обработку
                        answer_url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
                        requests.post(answer_url, json={"callback_query_id": query["id"]})
            
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"❌ Ошибка в обработке кнопок: {e}")
            time.sleep(5)

# Запускаем обработчик кнопок
callback_thread = Thread(target=handle_callback_updates, daemon=True)
callback_thread.start()

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        logger.info("📨 Получен заказ от storelend.ru")
        
        order_data_str = request.form.get('order_data')
        if not order_data_str:
            return jsonify({"status": "error", "message": "No order_data"}), 400
        
        import json
        order_data = json.loads(order_data_str)
        
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
    logger.info("✅ Сервер и обработчик кнопок запущены!")
    app.run(host='0.0.0.0', port=5000)
