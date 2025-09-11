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
            logger.error(f"Сырые данные: {raw_data}")
            logger.error(f"Заголовки: {dict(request.headers)}")
            return jsonify({"status": "error", "message": "Invalid data format"}), 400
        
        # Логируем распарсенные данные
        logger.info(f"📦 Распарсенные данные заказа: {order_data}")
        
        # Отправляем заказ в Telegram канал
        success = asyncio.run(send_order_to_channel(order_data))
        
        if success:
            logger.info(f"✅ Заказ #{order_data.get('id')} отправлен в Telegram")
            return jsonify({"status": "success", "message": "Order processed"})
        else:
            logger.error(f"❌ Ошибка отправки заказа #{order_data.get('id')} в Telegram")
            return jsonify({"status": "error", "message": "Telegram send failed"}), 500
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки webhook: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 400
