def send_to_telegram(order_data):
    try:
        # ... (остальной код формирования сообщения без изменений)

        # СОЗДАЕМ КНОПКИ КОТОРЫЕ НЕ ПРОПАДАЮТ
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Принял", "callback_data": f"accept_{order_data.get('order_num')}"},
                    {"text": "🚗 В пути", "callback_data": f"delivery_{order_data.get('order_num')}"},
                    {"text": "✅ Доставлен", "callback_data": f"delivered_{order_data.get('order_num')}"}
                ],
                [
                    {"text": "📞 Позвонить", "callback_data": f"call_{order_data.get('order_num')}"},
                    {"text": "❌ Отменить", "callback_data": f"cancel_{order_data.get('order_num')}"}
                ]
            ]
        }

        # ... (остальной код без изменений)

def handle_callback_updates():
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=30"
            response = requests.get(url, timeout=35)
            data = response.json()
            
            if data["ok"] and data["result"]:
                for update in data["result"]:
                    if "callback_query" in update:
                        query = update["callback_query"]
                        callback_data = query["data"]
                        username = query["from"].get("username", query["from"]["first_name"])
                        order_num = callback_data.split("_")[1]
                        
                        original_text = query["message"]["text"]
                        
                        # Убираем предыдущие статусы если есть
                        lines = original_text.split('\n')
                        cleaned_text = '\n'.join([line for line in lines if not any(x in line for x in ['✅ Принял:', '🚗 В пути:', '✅ Доставлен:', '❌ Отменен:'])])
                        
                        if callback_data.startswith("accept_"):
                            new_text = cleaned_text + f"\n\n✅ Принял: @{username}"
                        elif callback_data.startswith("delivery_"):
                            new_text = cleaned_text + f"\n\n🚗 В пути: @{username}"
                        elif callback_data.startswith("delivered_"):
                            new_text = cleaned_text + f"\n\n✅ Доставлен: @{username}"
                        elif callback_data.startswith("cancel_"):
                            new_text = cleaned_text + f"\n\n❌ Отменен: @{username}"
                        elif callback_data.startswith("call_"):
                            # Для кнопки "Позвонить" просто отвечаем
                            answer_url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
                            requests.post(answer_url, json={"callback_query_id": query["id"], "text": "Нажмите на номер телефона выше ☝️"})
                            continue
                        
                        # ОБНОВЛЯЕМ СООБЩЕНИЕ БЕЗ УДАЛЕНИЯ КНОПОК
                        edit_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
                        payload = {
                            "chat_id": CHANNEL_ID,
                            "message_id": query["message"]["message_id"],
                            "text": new_text,
                            "parse_mode": "HTML",
                            "reply_markup": query["message"]["reply_markup"]  # Сохраняем кнопки!
                        }
                        requests.post(edit_url, json=payload)
                        
                        # Подтверждаем обработку
                        answer_url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
                        requests.post(answer_url, json={"callback_query_id": query["id"], "text": "Статус обновлен!"})
            
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"❌ Ошибка в обработке кнопок: {e}")
            time.sleep(5)
