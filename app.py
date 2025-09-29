from flask import Flask, request, jsonify
import requests
import logging
from datetime import datetime
import time
from threading import Thread, Lock
import re

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# КОНФИГУРАЦИЯ
BOT_TOKEN = "8338994662:AAH7FALz3qd3F9dzcPadCVQY6CRPBXtFxiA"
CHANNEL_ID = "-10031287885760"

# Словарь для отслеживания статусов заказов
orders_status = {}
status_lock = Lock()

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

        # Кнопки
        order_num = order_data.get('order_num', '')
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Принять", "callback_data": f"accept_{order_num}"},
                    {"text": "🚗 В пути", "callback_data": f"delivery_{order_num}"}
                ],
                [
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

def handle_callback_updates():
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=10"
            response = requests.get(url, timeout=15)
            data = response.json()
            
            if data["ok"] and data["result"]:
                for update in data["result"]:
                    if "callback_query" in update:
                        query = update["callback_query"]
                        callback_data = query["data"]
                        user_id = query["from"]["id"]
                        username = query["from"].get("username", query["from"]["first_name"])
                        
                        if callback_data.startswith(("accept_", "delivery_", "delivered_")):
                            order_num = callback_data.split("_")[1]
                            message_id = query["message"]["message_id"]
                            current_text = query["message"]["text"]
                            
                            with status_lock:
                                current_status = orders_status.get(order_num, {})
                                
                                # ПРОВЕРКА ПРАВИЛ
                                can_perform_action = False
                                action_type = callback_data.split("_")[0]
                                
                                if action_type == "accept":
                                    if "status" not in current_status:
                                        can_perform_action = True
                                        orders_status[order_num] = {
                                            "status": "accepted", 
                                            "courier_id": user_id,
                                            "courier_name": username
                                        }
                                    
                                elif action_type == "delivery":
                                    if (current_status.get("status") == "accepted" and 
                                        current_status.get("courier_id") == user_id):
                                        can_perform_action = True
                                        orders_status[order_num]["status"] = "delivery"
                                    
                                elif action_type == "delivered":
                                    if (current_status.get("status") in ["accepted", "delivery"] and 
                                        current_status.get("courier_id") == user_id):
                                        can_perform_action = True
                                        orders_status[order_num]["status"] = "delivered"
                                
                                # ОБРАБОТКА ДЕЙСТВИЯ
                                if can_perform_action:
                                    # Обновляем текст сообщения
                                    status_texts = {
                                        "accept": f"\n\n✅ Принял: @{username}",
                                        "delivery": f"\n\n🚗 В пути: @{username}",
                                        "delivered": f"\n\n✅ Доставлен: @{username}"
                                    }
                                    
                                    # Удаляем предыдущие статусы
                                    cleaned_text = re.sub(r'\n\n✅ Принял:.*|\n\n🚗 В пути:.*|\n\n✅ Доставлен:.*', '', current_text)
                                    new_text = cleaned_text + status_texts[action_type]
                                    
                                    # Обновляем сообщение
                                    edit_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
                                    payload = {
                                        "chat_id": CHANNEL_ID,
                                        "message_id": message_id,
                                        "text": new_text,
                                        "parse_mode": "HTML",
                                        "reply_markup": query["message"]["reply_markup"],
                                        "disable_web_page_preview": True
                                    }
                                    requests.post(edit_url, json=payload)
                                    
                                    # Успешный ответ
                                    answer_url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
                                    requests.post(answer_url, json={
                                        "callback_query_id": query["id"],
                                        "text": "✅ Статус обновлен!"
                                    })
                                    
                                else:
                                    # Ошибка - действие нельзя выполнить
                                    error_messages = {
                                        "accept": "❌ Этот заказ уже взят другим курьером!",
                                        "delivery": "❌ Сначала нужно принять заказ!",
                                        "delivered": "❌ Нельзя отметить доставленным чужой заказ!"
                                    }
                                    
                                    answer_url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
                                    requests.post(answer_url, json={
                                        "callback_query_id": query["id"],
                                        "text": error_messages.get(action_type, "❌ Действие невозможно!"),
                                        "show_alert": True
                                    })
            
            time.sleep(2)
            
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
    logger.info("✅ Сервер запущен! Умный обработчик кнопок активен!")
    app.run(host='0.0.0.0', port=5000)
