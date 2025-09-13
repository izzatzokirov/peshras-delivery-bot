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
orders_lock = Lock()  # Блокировка для избежания гонки условий

def send_to_telegram(order_data):
    # ... (ваш существующий код без изменений) ...

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
                            action_type = callback_data.split("_")[0]
                            
                            # ОБРАБОТКА С БЛОКИРОВКОЙ
                            with orders_lock:  # Важно: блокируем доступ к orders_status
                                current_status = orders_status.get(order_num, {})
                                
                                # ЛОГИКА ПРОВЕРОК
                                can_perform_action = False
                                error_message = ""
                                
                                if action_type == "accept":
                                    if "status" not in current_status:
                                        can_perform_action = True
                                        orders_status[order_num] = {
                                            "status": "accepted", 
                                            "courier_id": user_id,
                                            "courier_name": username
                                        }
                                    else:
                                        error_message = "❌ Заказ уже принят!"
                                    
                                elif action_type == "delivery":
                                   
