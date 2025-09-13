from flask import Flask, request, jsonify
import requests
import logging
from datetime import datetime
import time
import re

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# КОНФИГУРАЦИЯ
BOT_TOKEN = "8338994662:AAH7FALz3qd3F9dzcPadCVQY6CRPBXtFxiA"
CHANNEL_ID = "-1002967095913"

# Для хранения статусов заказов
orders_status = {}
processed_orders = {}

def send_to_telegram(order_data):
    try:
        order_num = order_data.get('order_num')
        
        # Защита от дубликатов
        current_time = time.time()
        if order_num in processed_orders:
            if current_time - processed_orders[order_num] < 300:
                logger.warning(f"⚠️ Дубликат заказа #{order_num} - игнорируем")
                return True
        
        processed_orders[order_num] = current_time
        
        # Формируем сообщение
        message = f"🛒 Заказ #{order_num}\n\n"
        
        # Товары
        if 'line' in order_data and isinstance(order_data['line'], list):
            for i, item in enumerate(order_data['line'], 1):
                if item.get('order_line_type_id') == 1:
                    name = item.get('order_line_name', 'Товар')
                    quantity = item.get('order_line_quantity', 1)
                    art = item.get('order_line_art_number', 'без артикула')
                    message += f"{i}. {name} {quantity}шт. арт {art}\n"
        
        # Информация о заказе
        payment_method = order_data.get('payment_name', 'Наличные')
        message += f"\n💰 Сумма: {order_data.get('order_sum', 0)} сомони"
        message += f"\n💳 Оплата: {payment_method}"
        
        phone = order_data.get('order_phone', '')
        if phone:
            message += f"\n📞 Телефон: <a href=\"tel:{phone}\">{phone}</a>"
        
        message += f"\n👤 Имя: {order_data.get('order_person', 'N/A')}"
        message += f"\n🏠 Адрес: {order_data.get('order_address', 'N/A')}"
        message += f"\n⏰ Время: {convert_unix_time(order_data.get('order_time', ''))}"
        
        comment = order_data.get('order_comment', '')
        if comment:
            message += f"\n💬 Комментарий: {comment}"

        # Кнопки для нового заказа
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Принять", "callback_data": f"accept_{order_num}"},
                    {"text": "🚗 В пути", "callback_data": f"delivery_{order_num}"},
                    {"text": "✅ Доставлен", "callback_data": f"delivered_{order_num}"}
                ]
            ]
        }

        # Отправляем сообщение
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
        logger.error(f"❌ Ошибка отправки: {e}")
        return False

def convert_unix_time(unix_time):
    try:
        return datetime.fromtimestamp(int(unix_time)).strftime('%Y-%m-%d %H:%M:%S')
    except:
        return unix_time

def handle_callback(callback_data, user_id, username, message_id, current_text):
    """Обработка нажатий кнопок"""
    try:
        if callback_data.startswith(("accept_", "delivery_", "delivered_")):
            order_num = callback_data.split('_')[1]
            action_type = callback_data.split('_')[0]
            
            # Очищаем предыдущие статусы
            cleaned_text = re.sub(r'\n\n✅ Принял:.*|\n\n🚗 В пути:.*|\n\n✅ Доставлен:.*', '', current_text)
            
            if action_type == "accept":
                if order_num not in orders_status:
                    orders_status[order_num] = {
                        'status': 'accepted',
                        'courier_id': user_id,
                        'courier_name': username
                    }
                    new_text = cleaned_text + f"\n\n✅ Принял: @{username}"
                    new_keyboard = {
                        "inline_keyboard": [
                            [
                                {"text": "🚗 В пути", "callback_data": f"delivery_{order_num}"},
                                {"text": "✅ Доставлен", "callback_data": f"delivered_{order_num}"}
                            ]
                        ]
                    }
                    return update_message(message_id, new_text, new_keyboard)
            
            elif action_type == "delivery":
                if (order_num in orders_status and 
                    orders_status[order_num]['courier_id'] == user_id):
                    new_text = cleaned_text + f"\n\n🚗 В пути: @{username}"
                    new_keyboard = {
                        "inline_keyboard": [
                            [
                                {"text": "✅ Доставлен", "callback_data": f"delivered_{order_num}"}
                            ]
                        ]
                    }
                    return update_message(message_id, new_text, new_keyboard)
            
            elif action_type == "delivered":
                if (order_num in orders_status and 
                    orders_status[order_num]['courier_id'] == user_id):
                    new_text = cleaned_text + f"\n\n✅ Доставлен: @{username}"
                    new_keyboard = {"inline_keyboard": []}  # Убираем все кнопки
                    return update_message(message_id, new_text, new_keyboard)
            
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка обработки callback: {e}")
        return False

def update_message(message_id, text, keyboard):
    """Обновление сообщения в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
        payload = {
            "chat_id": CHANNEL_ID,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": keyboard,
            "disable_web_page_preview": True
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ Ошибка обновления сообщения: {e}")
        return False

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

# Обработчик для callback от Telegram
@app.route('/callback', methods=['POST'])
def callback():
    try:
        data = request.get_json()
        if 'callback_query' in data:
            query = data['callback_query']
            callback_data = query['data']
            user_id = query['from']['id']
            username = query['from'].get('username', query['from']['first_name'])
            message_id = query['message']['message_id']
            current_text = query['message']['text']
            
            success = handle_callback(callback_data, user_id, username, message_id, current_text)
            
            # Ответ для Telegram
            if success:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", 
                             json={"callback_query_id": query['id']})
            
            return jsonify({"status": "success"})
        
        return jsonify({"status": "error"}), 400
        
    except Exception as e:
        logger.error(f"❌ Ошибка callback: {e}")
        return jsonify({"status": "error"}), 500

@app.route('/')
def home():
    return "Peshras Delivery Bot is running!"

if __name__ == '__main__':
    logger.info("✅ Сервер запущен с работающими кнопками!")
    app.run(host='0.0.0.0', port=5000)
