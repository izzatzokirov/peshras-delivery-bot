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
orders_db = {}
processed_orders = {}

def send_to_telegram(order_data):
    try:
        order_num = order_data.get('order_num', 'N/A')
        
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
        message += f"\n⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
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
        
        if response.status_code == 200:
            # Сохраняем ID сообщения
            message_id = response.json()['result']['message_id']
            orders_db[order_num] = {
                'message_id': message_id,
                'status': 'new',
                'courier': None,
                'message_text': message
            }
            return True
        return False
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}")
        return False

def update_telegram_message(order_num, new_text, new_keyboard=None):
    """Обновляем сообщение в Telegram"""
    try:
        if order_num not in orders_db:
            return False
            
        message_id = orders_db[order_num]['message_id']
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
        payload = {
            "chat_id": CHANNEL_ID,
            "message_id": message_id,
            "text": new_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        if new_keyboard:
            payload["reply_markup"] = new_keyboard
        
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления сообщения: {e}")
        return False

def handle_order_action(order_num, action, username):
    """Обработка действий с заказом"""
    try:
        if order_num not in orders_db:
            return False, "Заказ не найден"
            
        current_status = orders_db[order_num]['status']
        current_courier = orders_db[order_num]['courier']
        
        # Проверяем возможность действия
        if action == "accept":
            if current_status != "new":
                return False, "Заказ уже взят"
                
            orders_db[order_num]['status'] = "accepted"
            orders_db[order_num]['courier'] = username
            
            new_text = orders_db[order_num]['message_text'] + f"\n\n✅ Принял: @{username}"
            new_keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "🚗 В пути", "callback_data": f"delivery_{order_num}"},
                        {"text": "✅ Доставлен", "callback_data": f"delivered_{order_num}"}
                    ]
                ]
            }
            
        elif action == "delivery":
            if current_status != "accepted" or current_courier != username:
                return False, "Нельзя изменить статус"
                
            orders_db[order_num]['status'] = "delivery"
            
            # Удаляем предыдущие статусы и добавляем новый
            original_text = orders_db[order_num]['message_text']
            cleaned_text = re.sub(r'\n\n✅ Принял:.*|\n\n🚗 В пути:.*|\n\n✅ Доставлен:.*', '', original_text)
            new_text = cleaned_text + f"\n\n🚗 В пути: @{username}"
            new_keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Доставлен", "callback_data": f"delivered_{order_num}"}
                    ]
                ]
            }
            
        elif action == "delivered":
            if current_status not in ["accepted", "delivery"] or current_courier != username:
                return False, "Нельзя отметить доставленным"
                
            orders_db[order_num]['status'] = "delivered"
            
            original_text = orders_db[order_num]['message_text']
            cleaned_text = re.sub(r'\n\n✅ Принял:.*|\n\n🚗 В пути:.*|\n\n✅ Доставлен:.*', '', original_text)
            new_text = cleaned_text + f"\n\n✅ Доставлен: @{username}"
            new_keyboard = {"inline_keyboard": []}  # Убираем все кнопки
            
        else:
            return False, "Неизвестное действие"
        
        # Обновляем сообщение в Telegram
        success = update_telegram_message(order_num, new_text, new_keyboard)
        if success:
            orders_db[order_num]['message_text'] = new_text
            return True, "Статус обновлен"
        else:
            return False, "Ошибка обновления"
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки действия: {e}")
        return False, "Ошибка системы"

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

# Обработчик кнопок через GET (простой и рабочий)
@app.route('/button/<action>/<order_num>/<username>')
def handle_button(action, order_num, username):
    try:
        logger.info(f"🔘 Нажата кнопка: {action} на заказ #{order_num} пользователем @{username}")
        
        success, message = handle_order_action(order_num, action, username)
        
        if success:
            return f"✅ {message}"
        else:
            return f"❌ {message}", 400
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки кнопки: {e}")
        return f"❌ Ошибка системы: {e}", 500

# Веб-интерфейс для тестирования кнопок
@app.route('/test_buttons')
def test_buttons():
    html = """
    <html>
    <body>
        <h2>Тест кнопок для заказа #836</h2>
        <p>Имитация разных курьеров:</p>
        <a href="/button/accept/836/Али" style="padding:10px;background:green;color:white;margin:5px;">Али: Принять</a>
        <a href="/button/delivery/836/Али" style="padding:10px;background:blue;color:white;margin:5px;">Али: В пути</a>
        <a href="/button/delivered/836/Али" style="padding:10px;background:red;color:white;margin:5px;">Али: Доставлен</a>
        <br>
        <a href="/button/accept/836/Ахмад" style="padding:10px;background:green;color:white;margin:5px;">Ахмад: Принять</a>
    </body>
    </html>
    """
    return html

@app.route('/')
def home():
    return "Peshras Delivery Bot is running! Кнопки работают!"

if __name__ == '__main__':
    logger.info("✅ Сервер запущен с рабочими кнопками!")
    app.run(host='0.0.0.0', port=5000)
