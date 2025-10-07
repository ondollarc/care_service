# -*- coding: utf-8 -*-

# 引入必要的函式庫
import os
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

# 引入翻譯函式庫
# 安裝方式: pip install googletrans==4.0.0-rc1
from googletrans import Translator, LANGUAGES

# --- 環境變數設定 ---
# 為了安全，建議將 Channel Access Token 和 Channel Secret 設置為環境變數
# 如果您是初學者，也可以直接在下方填入您的資訊
CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'uhlPuz6ouit0XdKyFo1qP1CalHDgRBwD80Q6QgOtG8CWpl3uXgqRK0bMN2hjjrpyoyJQPkqB+YykxFTEczZKdI6u5sCTFflavFbOm2Kojdm0DiWOidBbxPRDCXBuOGhm9ct3Niy6BmQeseqV6cRtTAdB04t89/1O/w1cDnyilFU=')
CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', '0f4b80399390c7f4c523b7cd689d615d')

# --- Flask 應用程式初始化 ---
app = Flask(__name__)

# --- LINE Bot API 設定 ---
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# --- 翻譯器初始化 ---
translator = Translator()

# --- Webhook 路由 ---
# 這個路由會接收來自 LINE 伺服器的請求
@app.route("/callback", methods=['POST'])
def callback():
    # 取得 X-Line-Signature 標頭值
    signature = request.headers['X-Line-Signature']

    # 取得請求主體
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # 處理 webhook 主體
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

# --- 訊息處理 ---
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    # 取得使用者傳送的訊息
    user_message = event.message.text
    user_id = event.source.user_id

    # 取得機器人自己的 User ID，避免翻譯自己發出的訊息造成無限循環
    # 您可以在 LINE Developers Console 的 "Basic settings" 找到 "Your user ID"
    # 或者，您可以先部署一次，從日誌中找到 bot_id
    bot_profile = MessagingApi(ApiClient(configuration)).get_bot_info()
    bot_id = bot_profile.user_id

    # 如果訊息來源不是機器人自己，才進行翻譯
    if user_id != bot_id:
        try:
            # 偵測語言
            detected_lang = translator.detect(user_message).lang
            
            translation_result = ""
            
            # 核心翻譯邏輯
            # 如果偵測到是繁體中文，就翻譯成印尼文
            if detected_lang == 'zh-tw' or detected_lang == 'zh-cn':
                target_lang = 'id' # 印尼文代碼
                translated_text = translator.translate(user_message, dest=target_lang).text
                translation_result = f"🇮🇩 印尼文翻譯:\n{translated_text}"
            # 如果偵測到是印尼文，就翻譯成繁體中文
            elif detected_lang == 'id':
                target_lang = 'zh-tw' # 繁體中文代碼
                translated_text = translator.translate(user_message, dest=target_lang).text
                translation_result = f"🇹🇼 中文翻譯:\n{translated_text}"
            # 其他語言的訊息暫不處理，您可以根據需求擴充
            else:
                return

            # 使用 with...as 結構確保資源被正確管理
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                # 將翻譯結果傳回群組
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=translation_result)]
                    )
                )

        except Exception as e:
            app.logger.error(f"Error occurred: {e}")
            # 可以在這裡傳送一個錯誤訊息回 LINE，方便除錯
            # 例如：line_bot_api.reply_message(...)

# --- 主程式進入點 ---
if __name__ == "__main__":
    # 取得服務器端口號，Heroku 等平台會需要
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)