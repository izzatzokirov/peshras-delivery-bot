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
CHANNEL_ID = "-1002967095913"

# Глобальные переменные для управления заказами
orders_status = {}
orders_lock = Lock()

def send_to_telegram(order_data):
    try:
        # ... (ваш существующий код формирования сообщения) ...
        # Оставляем без изменений

        # Кнопки для нового заказа
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

        # ... (остальной код отправки) ...

    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}")
        return False

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
                        message_id = query["message"]["message_id"]
                        current_text = query["message"]["text"]
                        
                        if callback_data.startswith(("accept_", "delivery_", "delivered_")):
                            order_num = callback_data.split("_")[1]
                            action_type = callback_data.split("_")[0]
                            
                            with orders_lock:
                                current_status = orders_status.get(order_num, {})
                                
                                # ПРОВЕРКА ВОЗМОЖНОСТИ ДЕЙСТВИЯ
                                can_perform_action = False
                                
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
                                    
                                    # ОПРЕДЕЛЯЕМ НОВЫЕ КНОПКИ В ЗАВИСИМОСТИ ОТ СТАТУСА
                                    new_keyboard = None
                                    
                                    if action_type == "accept":
                                        # После "Принять" оставляем только "В пути" и "Доставлен"
                                        new_keyboard = {
                                            "inline_keyboard": [
                                                [
                                                    {"text": "🚗 В пути", "callback_data": f"delivery_{order_num}"},
                                                    {"text": "✅ Доставлен", "callback_data": f"delivered_{order_num}"}
                                                ]
                                            ]
                                        }
                                    elif action_type == "delivery":
                                        # После "В пути" оставляем только "Доставлен"
                                        new_keyboard = {
                                            "inline_keyboard": [
                                                [
                                                    {"text": "✅ Доставлен", "callback_data": f"delivered_{order_num}"}
                                                ]
                                            ]
                                        }
                                    elif action_type == "delivered":
                                        # После "Доставлен" убираем все кнопки
                                        new_keyboard = {"inline_keyboard": []}
                                    
                                    # Обновляем сообщение
                                    edit_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
                                    payload = {
                                        "chat_id": CHANNEL_ID,
                                        "message_id": message_id,
                                        "text": new_text,
                                        "parse_mode": "HTML",
                                        "reply_markup": new_keyboard,
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

# ... (остальной код без изменений) ...
