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

# Для защиты от дубликатов
processed_orders = {}

def convert_unix_time(unix_time):
    """Конвертируем Unix время в нормальное"""
    try:
        return datetime.fromtimestamp(int(unix_time)).strftime('%Y-%m-%d %H:%M:%S')
    except:
        return "Время не указано"

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
        
        # Формируем сообщение с правильным временем
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
        
        # ИСПРАВЛЕНО: Используем время из заказа Storelend
        order_time = order_data.get('order_time', '')
        if order_time:
            message += f"\n⏰ Время: {convert_unix_time(order_time)}"
        else:
            message += f"\n⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        comment = order_data.get('order_comment', '')
        if comment:
            message += f"\n💬 Комментарий: {comment}"

        # ПРОСТЫЕ РАБОЧИЕ КНОПКИ-ССЫЛКИ
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Принял", 
                        "url": f"https://t.me/share/url?text=✅ Принял заказ {order_num} (Peshras)"
                    },
                    {
                        "text": "🚗 В пути", 
                        "url": f"https://t.me/share/url?text=🚗 В пути с заказом {order_num} (Peshras)"
                    }
                ],
                [
                    {
                        "text": "✅ Доставлен", 
                        "url": f"https://t.me/share/url?text=✅ Доставил заказ {order_num} (Peshras)"
                    }
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

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        logger.info("📨 Получен заказ от storelend.ru")
        
        order_data_str = request.form.get('order_data')
        if not order_data_str:
            return jsonify({"status": "error", "message": "No order_data"}), 400
        
        import json
        order_data = json.loads(order_data_str)
        
        # Логируем данные для отладки
        logger.info(f"📦 Данные заказа: {order_data}")
        
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
    return "Peshras Delivery Bot is running! Кнопки-ссылки работают!"

if __name__ == '__main__':
    logger.info("✅ Сервер запущен с рабочими кнопками-ссылками!")
    app.run(host='0.0.0.0', port=5000)
