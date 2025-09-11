from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, ContextTypes
from flask import Flask, request, jsonify
import os
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# КОНФИГУРАЦИЯ - ЗДЕСЬ ВАШИ ДАННЫЕ!
BOT_TOKEN = os.getenv("BOT_TOKEN", "8338994662:AAH7FALz3qd3F9dzcPadCVQY6CRPBXtFxiA")
CHANNEL_ID = os.getenv("CHANNEL_ID", "-1002108941132")

# Глобальная переменная для бота
bot_instance = None

def initialize_bot():
    """Инициализация бота - упрощенная версия"""
    global bot_instance
    try:
        from telegram import Bot
        bot_instance = Bot(token=BOT_TOKEN)
        logger.info("✅ Бот успешно инициализирован!")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации бота: {e}")
        return False

# Функция отправки заказа в канал
def send_order_to_channel(order_data):
    global bot_instance
    try:
        if bot_instance is None:
            logger.error("❌ Бот не инициализирован, пытаемся инициализировать...")
            if not initialize_bot():
                return False

        message_text = f"🛒 НОВЫЙ ЗАКАЗ #_{order_data.get('id', 'N/A')}_\n"
        message_text += f"👤 Имя: {order_data.get('customer_name', 'N/A')}\n"
        message_text += f"📞 Телефон: `{order_data.get('customer_phone', 'N/A')}`\n"
        message_text += f"🏠 Адрес: {order_data.get('customer_address', 'N/A')}\n\n"
        
        message_text += "📦 Состав заказа:\n"
        items = order_data.get('items', [])
        if isinstance(items, list):
            for item in items:
                message_text += f"• {item.get('name', 'Товар')} x {item.get('quantity', 1)} - {item.get('price', 0)} сомони\n"
        else:
            message_text += "• Информация о товарах недоступна\n"
        
        message_text += f"\n💵 Сумма: {order_data.get('total_amount', 0)} сомони\n"
        message_text += f"⏰ Время: {order_data.get('order_time', 'N/A')}\n"

        # Кнопки для курьеров (пока без обработки нажатий)
        keyboard = [
            [InlineKeyboardButton("✅ Принять заказ", callback_data="accept")],
            [InlineKeyboardButton("🚗 В пути", callback_data="delivery")],
            [InlineKeyboardButton("✅ Доставлен", callback_data="delivered")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправка в канал
        bot_instance.send_message(
            chat_id=CHANNEL_ID,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}")
        return False

# Webhook для приема заказов от storelend.ru
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        logger.info("📨 Получен запрос от storelend")
        
        # Пробуем получить данные
        order_data = {}
        
        # Пробуем JSON
        try:
            data = request.get_json()
            if data:
                if 'order_data' in data:
                    order_data = data['order_data']
                    logger.info("✅ Данные получены в формате JSON с order_data")
                else:
                    order_data = data
                    logger.info("✅ Данные получены как прямой JSON")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось распарсить как JSON: {e}")
        
        # Если данные не получены - пробуем form-data
        if not order_data:
            try:
                order_data_str = request.form.get('order_data')
                if order_data_str:
                    import json
                    order_data = json.loads(order_data_str)
                    logger.info("✅ Данные получены как form-data")
            except:
                pass
        
        # Если все еще нет данных - покажем сырые данные
        if not order_data:
            raw_data = request.get_data(as_text=True)
            logger.error(f"❌ Не удалось распарсить данные. Сырые данные: {raw_data}")
            return jsonify({"status": "error", "message": "Invalid data format"}), 400
        
        logger.info(f"📦 Данные заказа: {order_data}")
        
        # Отправляем заказ
        success = send_order_to_channel(order_data)
        
        if success:
            logger.info("✅ Заказ отправлен в Telegram")
            return jsonify({"status": "success", "message": "Order processed"})
        else:
            logger.error("❌ Ошибка отправки заказа в Telegram")
            return jsonify({"status": "error", "message": "Telegram send failed"}), 500
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

# Основной запуск
@app.route('/')
def home():
    return "Peshras Delivery Bot is running!"

# Инициализируем бот при запуске
if __name__ == '__main__':
    logger.info("🚀 Запуск приложения Peshras Delivery Bot...")
    
    # Инициализируем бота
    initialize_bot()
    
    app.run(host='0.0.0.0', port=5000, debug=False)
