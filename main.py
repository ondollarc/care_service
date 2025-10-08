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

# 引入翻譯與 AI 函式庫
from googletrans import Translator
import openai  # 改為使用 OpenAI 函式庫

app = Flask(__name__)

# --- 金鑰設定 ---
# LINE Bot 金鑰
CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '請在這裡填入您的 Channel Access Token')
CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', '請在這裡填入您的 Channel Secret')

# [新功能] OpenAI API 金鑰
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '請在這裡填入您的 OpenAI API Key')

# --- 檢查與初始化 ---
if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    print('請設定 LINE_CHANNEL_ACCESS_TOKEN 和 LINE_CHANNEL_SECRET 環境變數。')
    sys.exit(1)

# 如果有設定 OpenAI Key 才啟用 AI 功能
if OPENAI_API_KEY:
    try:
        openai.api_key = OPENAI_API_KEY
    except Exception as e:
        print(f"無法設定 OpenAI API: {e}")
        OPENAI_API_KEY = None # 如果金鑰有問題，則禁用此功能

handler = WebhookHandler(CHANNEL_SECRET)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

# --- 路由設定 ---
@app.route("/", methods=['GET'])
def home():
    return "OK, translator bot is alive."

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

# --- 核心邏輯 ---
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_message = event.message.text.strip()
    reply_message = ""

    # [新功能] 檢查是否觸發 AI 專家模式
    if OPENAI_API_KEY and user_message.startswith("看護助理"):
        question = user_message.replace("看護助理", "").strip()
        
        if not question:
            reply_message = "請在「看護助理」後面加上您想詢問的照護問題喔！"
        else:
            try:
                # 建立一個專業的指令，讓 AI 扮演照護專家的角色
                system_prompt = (
                    "您是一位非常有經驗的中風病人照護專家，特別了解如何指導外籍看護。 "
                    "請用繁體中文，以非常親切、有條理且專業的語氣，針對使用者的問題提供具體、可執行的照護建議。 "
                    "請將重點條列化，讓內容清晰易懂。在適當時機，請提醒看護應注意的風險或觀察重點。"
                )

                # 使用 OpenAI ChatCompletion API
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",  # 您也可以更換為 gpt-4 等其他模型
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": question}
                    ]
                )
                expert_advice = response.choices[0].message['content']
                
                reply_message = (
                    f"💡 照護專家建議 (Saran Ahli Perawatan):\n"
                    f"--------------------\n"
                    f"{expert_advice}"
                )
            except Exception:
                print(traceback.format_exc())
                reply_message = "抱歉，專家系統暫時無法連線，請稍後再試。"
    else:
        # 維持原有的翻譯功能
        try:
            translator = Translator()
            detected_lang = translator.detect(user_message).lang

            if detected_lang in ['zh-TW', 'zh-CN']:
                translated_text = translator.translate(user_message, dest='id').text
                reply_message = (
                    f"🇹🇼 原文 (Asli):\n{user_message}\n"
                    f"--------------------\n"
                    f"🇮🇩 翻譯 (Terjemahan):\n{translated_text}"
                )
            elif detected_lang == 'id':
                translated_text = translator.translate(user_message, dest='zh-TW').text
                reply_message = (
                    f"🇮🇩 Asli (原文):\n{user_message}\n"
                    f"--------------------\n"
                    f"🇹🇼 Terjemahan (中文翻譯):\n{translated_text}"
                )
            elif detected_lang == 'en':
                translated_text = translator.translate(user_message, dest='id').text
                reply_message = (
                    f"🇬🇧 Original (Asli):\n{user_message}\n"
                    f"--------------------\n"
                    f"🇮🇩 Translation (Terjemahan):\n{translated_text}"
                )
        except Exception:
            print(traceback.format_exc())
            # 翻譯失敗時不回覆，避免干擾
            return

    # 統一發送回覆訊息
    if reply_message:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_message)]
                )
            )

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

