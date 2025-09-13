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

def send_to_telegram(order_data):
    try:
        # Формируем сообщение
        message = f"🛒 Заказ #{order_data.get('order_num', 'N/A')}\n\n"
        
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

        # Кнопки для нового заказа (все видимые)
        order_num = order_data.get('order_num', '')
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

def update_message_with_new_buttons(message_id, new_text, new_keyboard):
    """Обновляем сообщение с новыми кнопками"""
    try:
        edit_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
        payload = {
            "chat_id": CHANNEL_ID,
            "message_id": message_id,
            "text": new_text,
            "parse_mode": "HTML",
            "reply_markup": new_keyboard,
            "disable_web_page_preview": True
        }
        response = requests.post(edit_url, json=payload, timeout=10)
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

# Простой обработчик кнопок (без многопоточности)
@app.route('/callback', methods=['POST'])
def callback_handler():
    try:
        data = request.json
        if 'callback_query' in data:
            query = data['callback_query']
            callback_data = query['data']
            user_id = query['from']['id']
            username = query['from'].get('username', query['from']['first_name'])
            message_id = query['message']['message_id']
            current_text = query['message']['text']
            
            if callback_data.startswith(("accept_", "delivery_", "delivered_")):
                order_num = callback_data.split('_')[1]
                action_type = callback_data.split('_')[0]
                
                # Обработка разных действий
                if action_type == "accept":
                    # Проверяем, не принят ли уже заказ
                    if order_num not in orders_status:
                        orders_status[order_num] = {
                            'status': 'accepted',
                            'courier_id': user_id,
                            'courier_name': username
                        }
                        
                        # Обновляем текст и кнопки
                        new_text = current_text + f"\n\n✅ Принял: @{username}"
                        new_keyboard = {
                            "inline_keyboard": [
                                [
                                    {"text": "🚗 В пути", "callback_data": f"delivery_{order_num}"},
                                    {"text": "✅ Доставлен", "callback_data": f"delivered_{order_num}"}
                                ]
                            ]
                        }
                        
                        if update_message_with_new_buttons(message_id, new_text, new_keyboard):
                            return jsonify({"status": "success"})
                
                elif action_type == "delivery":
                    # Проверяем, что заказ принят этим курьером
                    if (order_num in orders_status and 
                        orders_status[order_num]['courier_id'] == user_id):
                        
                        new_text = re.sub(r'\n\n✅ Принял:.*|\n\n🚗 В пути:.*|\n\n✅ Доставлен:.*', '', current_text)
                        new_text += f"\n\n🚗 В пути: @{username}"
                        new_keyboard = {
                            "inline_keyboard": [
                                [
                                    {"text": "✅ Доставлен", "callback_data": f"delivered_{order_num}"}
                                ]
                            ]
                        }
                        
                        if update_message_with_new_buttons(message_id, new_text, new_keyboard):
                            return jsonify({"status": "success"})
                
                elif action_type == "delivered":
                    # Проверяем, что заказ принят этим курьером
                    if (order_num in orders_status and 
                        orders_status[order_num]['courier_id'] == user_id):
                        
                        new_text = re.sub(r'\n\n✅ Принял:.*|\n\n🚗 В пути:.*|\n\n✅ Доставлен:.*', '', current_text)
                        new_text += f"\n\n✅ Доставлен: @{username}"
                        new_keyboard = {"inline_keyboard": []}  # Убираем все кнопки
                        
                        if update_message_with_new_buttons(message_id, new_text, new_keyboard):
                            return jsonify({"status": "success"})
                
                return jsonify({"status": "error", "message": "Действие невозможно"}), 400
        
        return jsonify({"status": "success"})
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки callback: {e}")
        return jsonify({"status": "error"}), 500

@app.route('/')
def home():
    return "Peshras Delivery Bot is running!"

if __name__ == '__main__':
    logger.info("✅ Сервер запущен!")
    app.run(host='0.0.0.0', port=5000)
