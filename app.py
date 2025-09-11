from flask import Flask, request, jsonify
import requests
import os
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# КОНФИГУРАЦИЯ - ВАШИ ДАННЫЕ
BOT_TOKEN = "8338994662:AAH7FALz3qd3F9dzcPadCVQY6CRPBXtFxiA"
CHANNEL_ID = "@peshras24"

# Функция отправки сообщения в Telegram
def send_to_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHANNEL_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        
        logger.info(f"📤 Отправляем сообщение в Telegram: {payload}")
        
        response = requests.post(url, json=payload, timeout=10)
        response_data = response.json()
        
        logger.info(f"📨 Ответ от Telegram API: {response_data}")
        
        if response.status_code == 200 and response_data.get('ok'):
            return True
        else:
            logger.error(f"❌ Ошибка Telegram API: {response_data}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка отправки в Telegram: {str(e)}")
        return False

# Webhook для приема заказов
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        logger.info("📨 Получен запрос от storelend")
        
        # Логируем заголовки для отладки
        logger.info(f"📋 Заголовки: {dict(request.headers)}")
        
        # Получаем form-data
        order_data_str = request.form.get('order_data')
        
        if not order_data_str:
            raw_data = request.get_data(as_text=True)
            logger.error(f"❌ Нет order_data в form-data. Все данные: {raw_data}")
            return jsonify({"status": "error", "message": "No order_data provided"}), 400
        
        # Парсим JSON из order_data
        try:
            import json
            order_data = json.loads(order_data_str)
            logger.info(f"✅ Данные заказа: {order_data}")
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}, данные: {order_data_str}")
            return jsonify({"status": "error", "message": "Invalid JSON format"}), 400
        
        # Формируем сообщение для Telegram
        message = f"🛒 <b>НОВЫЙ ЗАКАЗ</b> #{order_data.get('id', 'N/A')}\n"
        message += f"👤 <b>Имя:</b> {order_data.get('customer_name', 'N/A')}\n"
        message += f"📞 <b>Телефон:</b> {order_data.get('customer_phone', 'N/A')}\n"
        message += f"🏠 <b>Адрес:</b> {order_data.get('customer_address', 'N/A')}\n\n"
        
        message += "📦 <b>Состав заказа:</b>\n"
        items = order_data.get('items', [])
        if isinstance(items, list):
            for item in items:
                message += f"• {item.get('name', 'Товар')} x {item.get('quantity', 1)} - {item.get('price', 0)} сомони\n"
        else:
            message += "• Информация о товарах недоступна\n"
        
        message += f"\n💵 <b>Сумма:</b> {order_data.get('total_amount', 0)} сомони\n"
        message += f"⏰ <b>Время:</b> {order_data.get('order_time', 'N/A')}\n\n"
        
        message += "⚡ <i>Курьеры: ответьте на это сообщение чтобы взять заказ</i>"
        
        # Отправляем в Telegram
        success = send_to_telegram(message)
        
        if success:
            logger.info("✅ Заказ отправлен в Telegram")
            return jsonify({"status": "success", "message": "Order processed"})
        else:
            logger.error("❌ Ошибка отправки в Telegram")
            return jsonify({"status": "error", "message": "Telegram send failed"}), 500
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

# Статус сервера
@app.route('/')
def home():
    return "Peshras Delivery Bot is running!"

if __name__ == '__main__':
    logger.info("🚀 Сервер запущен!")
    app.run(host='0.0.0.0', port=5000, debug=False)
