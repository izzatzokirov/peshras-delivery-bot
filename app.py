from flask import Flask, request, jsonify
import requests
import logging
from datetime import datetime
import time

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# КОНФИГУРАЦИЯ
BOT_TOKEN = "8338994662:AAH7FALz3qd3F9dzcPadCVQY6CRPBXtFxiA"
CHANNEL_ID = "-1002967095913"

# Для хранения статусов
orders_db = {}
last_updates = {}

def send_to_telegram(order_data):
    try:
        order_num = order_data.get('order_num', 'N/A')
        
        # Защита от дубликатов
        current_time = time.time()
        if order_num in last_updates:
            if current_time - last_updates[order_num] < 300:
                logger.warning(f"⚠️ Дубликат заказа #{order_num} - игнорируем")
                return True
        
        last_updates[order_num] = current_time
        
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
        message += f"\n💰 Сумма: {order_data.get('order_sum', 0)} сомони"
        message += f"\n💳 Оплата: {order_data.get('payment_name', 'Наличные')}"
        
        phone = order_data.get('order_phone', '')
        if phone:
            message += f"\n📞 Телефон: <a href=\"tel:{phone}\">{phone}</a>"
        
        message += f"\n👤 Имя: {order_data.get('order_person', 'N/A')}"
        message += f"\n🏠 Адрес: {order_data.get('order_address', 'N/A')}"
        message += f"\n⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        comment = order_data.get('order_comment', '')
        if comment:
            message += f"\n💬 Комментарий: {comment}"

        # Кнопки
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
            # Сохраняем ID сообщения для дальнейшего обновления
            message_id = response.json()['result']['message_id']
            orders_db[order_num] = {
                'message_id': message_id,
                'status': 'new',
                'courier': None
            }
            return True
        return False
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}")
        return False

def update_buttons(order_num, status, username):
    """Обновляем кнопки после нажатия"""
    try:
        if order_num not in orders_db:
            return False
            
        message_id = orders_db[order_num]['message_id']
        orders_db[order_num]['status'] = status
        orders_db[order_num]['courier'] = username
        
        # Получаем текущий текст сообщения
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChat?chat_id={CHANNEL_ID}"
        response = requests.get(url)
        
        # Обновляем сообщение с новыми кнопками
        edit_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageReplyMarkup"
        
        if status == 'accepted':
            new_keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "🚗 В пути", "callback_data": f"delivery_{order_num}"},
                        {"text": "✅ Доставлен", "callback_data": f"delivered_{order_num}"}
                    ]
                ]
            }
        elif status == 'delivery':
            new_keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Доставлен", "callback_data": f"delivered_{order_num}"}
                    ]
                ]
            }
        else:  # delivered
            new_keyboard = {"inline_keyboard": []}  # Убираем все кнопки
        
        payload = {
            "chat_id": CHANNEL_ID,
            "message_id": message_id,
            "reply_markup": new_keyboard
        }
        
        response = requests.post(edit_url, json=payload)
        return response.status_code == 200
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления кнопок: {e}")
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

# Обработчик кнопок
@app.route('/button/<action>/<order_num>/<username>')
def handle_button(action, order_num, username):
    try:
        if order_num not in orders_db:
            return "❌ Заказ не найден", 400
        
        current_status = orders_db[order_num]['status']
        
        if action == "accept" and current_status == "new":
            success = update_buttons(order_num, "accepted", username)
            return "✅ Заказ принят!" if success else "❌ Ошибка"
            
        elif action == "delivery" and current_status == "accepted":
            success = update_buttons(order_num, "delivery", username)
            return "🚗 Заказ в пути!" if success else "❌ Ошибка"
            
        elif action == "delivered" and current_status in ["accepted", "delivery"]:
            success = update_buttons(order_num, "delivered", username)
            return "✅ Заказ доставлен!" if success else "❌ Ошибка"
            
        return "❌ Действие невозможно", 400
        
    except Exception as e:
        return f"❌ Ошибка: {e}", 500

@app.route('/')
def home():
    return "Peshras Delivery Bot is running!"

if __name__ == '__main__':
    logger.info("✅ Сервер запущен с работающими кнопками!")
    app.run(host='0.0.0.0', port=5000)
