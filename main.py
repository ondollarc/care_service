import os
import sys
import traceback
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# 引入 googletrans 翻譯函式庫
from googletrans import Translator

app = Flask(__name__)

# 從環境變數讀取金鑰，若找不到則使用您填寫的預設值
CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '請在這裡填入您的 Channel Access Token')
CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', '請在這裡填入您的 Channel Secret')

if CHANNEL_ACCESS_TOKEN is None or CHANNEL_SECRET is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET as environment variables.')
    sys.exit(1)

handler = WebhookHandler(CHANNEL_SECRET)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

# [新功能] 新增一個根目錄路由，專門給 cron-job 服務檢查用
@app.route("/", methods=['GET'])
def home():
    return "OK, translator bot is alive."

# 主路由，接收來自 LINE 的訊息
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 處理文字訊息的函式
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_message = event.message.text
    reply_message = ""

    try:
        # 每次收到訊息時，都重新建立一個 Translator 物件
        # 這可以提高 googletrans 函式庫的穩定性，避免因連線問題導致的無聲失敗
        translator = Translator()

        # 偵測語言
        detected_lang = translator.detect(user_message).lang

        if detected_lang == 'zh-TW' or detected_lang == 'zh-CN':
            # 翻譯成印尼文
            translated_text = translator.translate(user_message, dest='id').text
            # 訊息格式包含原文與翻譯
            reply_message = (
                f"🇹🇼 原文 (Asli):\n{user_message}\n"
                f"--------------------\n"
                f"🇮🇩 翻譯 (Terjemahan):\n{translated_text}"
            )
        elif detected_lang == 'id':
            # 翻譯成繁體中文
            translated_text = translator.translate(user_message, dest='zh-TW').text
            # 訊息格式包含原文與翻譯
            reply_message = (
                f"🇮🇩 Asli (原文):\n{user_message}\n"
                f"--------------------\n"
                f"🇹🇼 Terjemahan (中文翻譯):\n{translated_text}"
            )
        
        # 如果有成功產生翻譯訊息，才進行回覆
        if reply_message:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply_message)]
                    )
                )

    except Exception as e:
        # 當發生任何錯誤時，在 Render 的日誌中印出詳細的錯誤訊息
        # 這將幫助我們未來能準確地找到問題
        print("An error occurred during translation or reply:")
        print(traceback.format_exc())

# 讓 gunicorn 可以執行
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

