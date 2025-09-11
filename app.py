from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

BOT_TOKEN = '8338994662:AAH7FALz3qd3F9dzcPadCVQY6CRPBXtFxiA'
CHANNEL_ID = '-1002108941132'

def send_to_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHANNEL_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        requests.post(url, json=payload)
        return True
    except:
        return False

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        order_data = data.get('order_data', {})
        
        message = f"🛒 <b>НОВЫЙ ЗАКАЗ #{order_data.get('id', 'N/A')}</b>\n"
        message += f"👤 <b>Имя:</b> {order_data.get('customer_name', 'N/A')}\n"
        message += f"📞 <b>Телефон:</b> {order_data.get('customer_phone', 'N/A')}\n"
        message += f"🏠 <b>Адрес:</b> {order_data.get('customer_address', 'N/A')}\n\n"
        
        message += "✅ Для принятия заказа ответьте на это сообщение"

        if send_to_telegram(message):
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error"}), 500

    except Exception as e:
        return jsonify({"status": "error"}), 400

@app.route('/')
def home():
    return "Peshras Bot Working!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
