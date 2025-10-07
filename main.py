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
CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'uhlPuz6ouit0XdKyFo1qP1CalHDgRBwD80Q6QgOtG8CWpl3uXgqRK0bMN2hjjrpyoyJQPkqB+YykxFTEczZKdI6u5sCTFflavFbOm2Kojdm0DiWOidBbxPRDCXBuOGhm9ct3Niy6BmQeseqV6cRtTAdB04t89/1O/w1cDnyilFU=')
CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', '0f4b80399390c7f4c523b7cd689d615d')

if CHANNEL_ACCESS_TOKEN is None or CHANNEL_SECRET is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET as environment variables.')
    sys.exit(1)

handler = WebhookHandler(CHANNEL_SECRET)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

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
        # [重要修正] 每次收到訊息時，都重新建立一個 Translator 物件
        # 這可以提高 googletrans 函式庫的穩定性，避免因連線問題導致的無聲失敗
        translator = Translator()

        # 偵測語言
        detected_lang = translator.detect(user_message).lang

        if detected_lang == 'zh-TW' or detected_lang == 'zh-CN':
            # 翻譯成印尼文
            translated_text = translator.translate(user_message, dest='id').text
            reply_message = f"🇮🇩 Terjemahan:\n{translated_text}"
        elif detected_lang == 'id':
            # 翻譯成繁體中文
            translated_text = translator.translate(user_message, dest='zh-TW').text
            reply_message = f"🇹🇼 中文翻譯:\n{translated_text}"
        
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
        # [重要修正] 當發生任何錯誤時，在 Render 的日誌中印出詳細的錯誤訊息
        # 這將幫助我們未來能準確地找到問題
        print("An error occurred during translation or reply:")
        print(traceback.format_exc())

# 讓 gunicorn 可以執行
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

