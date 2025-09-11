from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, ContextTypes
from flask import Flask, request, jsonify
import os
import logging
import threading

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# КОНФИГУРАЦИЯ - ЗДЕСЬ ВАШИ ДАННЫЕ!
BOT_TOKEN = os.getenv("BOT_TOKEN", "8338994662:AAH7FALz3qd3F9dzcPadCVQY6CRPBXtFxiA")
CHANNEL_ID = os.getenv("CHANNEL_ID", "-1002108941132")

# Глобальная переменная для бота
bot_application = None

def run_bot():
    """Запуск бота в отдельном потоке"""
    global bot_application
    try:
        bot_application = Application.builder().token(BOT_TOKEN).build()
        bot_application.add_handler(CallbackQueryHandler(button_handler))
        logger.info("✅ Бот инициализирован, запускаем polling...")
        bot_application.run_polling()
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")

# Запускаем бот в отдельном потоке при старте
bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()

# Функция отправки заказа в канал
def send_order_to_channel(order_data):
    try:
        if bot_application is None:
            logger.error("❌ Бот не инициализирован")
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

        # Кнопки для курьеров
        keyboard = [
            [InlineKeyboardButton("✅ Принять заказ", callback_data=f"accept_{order_data.get('id', '')}")],
            [InlineKeyboardButton("🚗 В пути", callback_data=f"delivery_{order_data.get('id', '')}")],
            [InlineKeyboardButton("✅ Доставлен", callback_data=f"delivered_{order_data.get('id', '')}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправка в канал
        bot_application.bot.send_message(
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
        # Логируем сырые данные для отладки
        raw_data = request.get_data(as_text=True)
        logger.info(f"📨 Получены сырые данные: {raw_data}")
        
        # Пробуем разные форматы данных
        order_data = {}
        
        # Вариант 1: JSON с полем order_data
        try:
            data = request.json
            if data and 'order_data' in data:
                order_data = data['order_data']
                logger.info("✅ Данные получены в формате JSON с order_data")
        except:
            pass
        
        # Вариант 2: Прямой JSON в теле запроса
        if not order_data:
            try:
                order_data = request.json
                if order_data:
                    logger.info("✅ Данные получены как прямой JSON")
            except:
                pass
        
        # Вариант 3: Form-data или другие форматы
        if not order_data:
            try:
                # Пробуем получить как form-data
                order_data_str = request.form.get('order_data')
                if order_data_str:
                    import json
                    order_data = json.loads(order_data_str)
                    logger.info("✅ Данные получены как form-data")
            except:
                pass
        
        # Если все варианты не сработали
        if not order_data:
            logger.error("❌ Не удалось распарсить данные заказа")
            return jsonify({"status": "error", "message": "Invalid data format"}), 400
        
        # Отправляем заказ в Telegram канал
        success = send_order_to_channel(order_data)
        
        if success:
            logger.info(f"✅ Заказ #{order_data.get('id')} отправлен в Telegram")
            return jsonify({"status": "success", "message": "Order processed"})
        else:
            logger.error(f"❌ Ошибка отправки заказа #{order_data.get('id')} in Telegram")
            return jsonify({"status": "error", "message": "Telegram send failed"}), 500
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

# Обработчик кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    username = query.from_user.username or query.from_user.first_name
    
    if callback_data.startswith('accept_'):
        await query.edit_message_text(text=f"{query.message.text}\n\n✅ Принял: @{username}")
    elif callback_data.startswith('delivery_'):
        await query.edit_message_text(text=f"{query.message.text}\n\n🚗 В пути: @{username}")
    elif callback_data.startswith('delivered_'):
        await query.edit_message_text(text=f"{query.message.text}\n\n✅ Доставлен: @{username}")

# Основной запуск
@app.route('/')
def home():
    return "Peshras Delivery Bot is running!"

if __name__ == '__main__':
    logger.info("🚀 Запуск приложения Peshras Delivery Bot...")
    app.run(host='0.0.0.0', port=5000, debug=False)
