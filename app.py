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

# Функция отправки в Telegram с кнопками
def send_to_telegram(order_data):
    try:
        # Формируем сообщение
        message = f"🛒 <b>НОВЫЙ ЗАКАЗ</b> #{order_data.get('order_num', 'N/A')}\n"
        message += f"👤 <b>Имя:</b> {order_data.get('order_person', 'N/A')}\n"
        message += f"📞 <b>Телефон:</b> {order_data.get('order_phone', 'N/A')}\n"
        message += f"🏠 <b>Адрес:</b> {order_data.get('order_city', 'N/A')}, {order_data.get('order_address', 'N/A')}\n"
        message += f"💰 <b>Сумма:</b> {order_data.get('order_sum', 0)} сомони\n\n"
        
        message += "📦 <b>Состав заказа:</b>\n"
        if 'line' in order_data and isinstance(order_data['line'], list):
            for item in order_data['line']:
                if item.get('order_line_type_id') == 1:  # Только товары
                    message += f"• {item.get('order_line_name', 'Товар')} x {item.get('order_line_quantity', 1)} - {item.get('order_line_sum', 0)} сомони\n"
        
        message += f"\n⏰ <b>Время:</b> {convert_unix_time(order_data.get('order_time', ''))}\n"
        message += f"💬 <b>Комментарий:</b> {order_data.get('order_comment', 'Нет комментария')}\n"

        # Создаем кнопки для курьеров
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

        # Отправляем сообщение с кнопками
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

# Конвертация Unix time
def convert_unix_time(unix_time):
    try:
        return datetime.fromtimestamp(int(unix_time)).strftime('%Y-%m-%d %H:%M:%S')
    except:
        return unix_time

# Webhook для storelend.ru
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        logger.info("📨 Получен заказ от storelend.ru")
        
        # Получаем данные из form-data
        order_data_str = request.form.get('order_data')
        
        if not order_data_str:
            return jsonify({"status": "error", "message": "No order_data provided"}), 400
        
        # Парсим JSON
        import json
        order_data = json.loads(order_data_str)
        
        # Отправляем в Telegram с кнопками
        success = send_to_telegram(order_data)
        
        if success:
            logger.info(f"✅ Заказ #{order_data.get('order_num')} отправлен в Telegram")
            return jsonify({"status": "success", "message": "Order processed"})
        else:
            logger.error("❌ Ошибка отправки в Telegram")
            return jsonify({"status": "error", "message": "Telegram send failed"}), 500
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/')
def home():
    return "Peshras Delivery Bot is running!"

if __name__ == '__main__':
    logger.info("🚀 Сервер запущен!")
    app.run(host='0.0.0.0', port=5000, debug=False)
