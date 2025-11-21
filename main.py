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
import openai

app = Flask(__name__)

# --- 金鑰設定 ---
# LINE Bot 金鑰
CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '請在這裡填入您的 Channel Access Token')
CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', '請在這裡填入您的 Channel Secret')

# OpenAI API 金鑰
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '請在這裡填入您的 OpenAI API Key')

# --- 檢查與初始化 ---
if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    print('請設定 LINE_CHANNEL_ACCESS_TOKEN 和 LINE_CHANNEL_SECRET 環境變數。')
    sys.exit(1)

if OPENAI_API_KEY:
    try:
        openai.api_key = OPENAI_API_KEY
    except Exception as e:
        print(f"無法設定 OpenAI API: {e}")
        OPENAI_API_KEY = None

handler = WebhookHandler(CHANNEL_SECRET)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

# --- 輔助函式：AI 智慧翻譯 ---
def ai_translate(text, source_lang, target_lang):
    """
    使用 OpenAI 進行智慧翻譯
    特色：針對中文翻印尼文，會自動加上祝福語。
    """
    if not OPENAI_API_KEY:
        raise Exception("No OpenAI Key")

    system_prompt = ""
    
    if source_lang == 'zh-TW' and target_lang == 'id':
        # [修改點 1] 中文 -> 印尼文：要求通順並加上祝福
        system_prompt = (
            "You are a warm and professional translator. "
            "Translate the following Traditional Chinese text into natural, polite, and fluent Indonesian (Bahasa Indonesia). "
            "Context: Communication between a Taiwanese employer and an Indonesian caregiver. "
            "IMPORTANT: At the end of the translation, automatically add a short, culturally appropriate Indonesian blessing or encouraging phrase based on the context (e.g., 'Semoga sehat selalu', 'Tetap semangat', 'Terima kasih banyak'). "
            "Output only the translation followed by the blessing."
        )
    elif source_lang == 'id' and target_lang == 'zh-TW':
        # 印尼文 -> 中文：要求精準理解口語
        system_prompt = (
            "You are a professional translator specializing in Indonesian to Traditional Chinese (Taiwan). "
            "The input text may be informal Indonesian (Bahasa Gaul) or contain typos. "
            "Please interpret the intent correctly and translate it into natural, fluent Traditional Chinese suitable for daily communication. "
            "Do not explain, just provide the translation."
        )
    else:
        system_prompt = f"Translate the following text from {source_lang} to {target_lang}. Output only the translation."

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        temperature=0.4, # 稍微增加一點創意，讓祝福語自然
    )
    return response.choices[0].message['content'].strip()

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
    translator = Translator()

    # 定義觸發 AI 的關鍵字
    trigger_keyword_ch = "看護助理"
    trigger_keyword_id = "Asisten Perawat"

    question = ""
    is_ai_request = False

    user_message_lower = user_message.lower()
    if user_message_lower.startswith(trigger_keyword_ch): 
        is_ai_request = True
        question = user_message[len(trigger_keyword_ch):].strip()
    elif user_message_lower.startswith(trigger_keyword_id.lower()):
        is_ai_request = True
        question = user_message[len(trigger_keyword_id):].strip()

    # --- 模式 A: AI 全能助理模式 (擴充功能) ---
    if OPENAI_API_KEY and is_ai_request:
        if not question:
            reply_message = (
                "我是您的全能生活與照護助理！\n"
                "您可以問我照護問題、生活大小事，甚至叫我講笑話喔！\n\n"
                "Halo! Saya asisten kehidupan dan perawatan Anda. "
                "Anda bisa bertanya tentang perawatan, kehidupan sehari-hari, atau minta saya bercanda!"
            )
        else:
            try:
                detected_lang = translator.detect(question).lang
                
                system_prompt = ""
                response_lang_instruction = ""

                # [修改點 2] 擴充 System Prompt：涵蓋照護、生活、笑話、幽默感
                base_persona = (
                    "You are a warm, humorous, and professional home care assistant. "
                    "Your primary expertise is stroke patient care, but you are also a general life assistant. "
                    "You can answer questions about daily life (groceries, household tips), tell jokes to lighten the mood, and provide emotional support. "
                    "Tone: Friendly, encouraging, and polite."
                )

                if detected_lang in ['zh-TW', 'zh-CN']:
                    system_prompt = (
                        f"{base_persona} "
                        "請用繁體中文回答。如果是照護問題，請提供專業且條理分明的建議；"
                        "如果是要求講笑話，請提供一個適合台灣家庭的幽默笑話；"
                        "如果是生活問題，請給予實用的生活小撇步。"
                    )
                    response_lang_instruction = " (生活與照護助理)"
                else:
                    # 針對印尼語使用者的 Prompt
                    system_prompt = (
                        f"{base_persona} "
                        "Please respond in Bahasa Indonesia. "
                        "If it's a care question, provide clear, actionable advice using bullet points. "
                        "If asked for a joke, tell a funny, culturally appropriate Indonesian joke. "
                        "If it's a daily life question, give practical tips. "
                        "Always be encouraging."
                    )
                    response_lang_instruction = " (Asisten Harian & Perawatan)"

                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": question}
                    ]
                )
                expert_advice = response.choices[0].message['content']
                
                reply_message = f"💡 {response_lang_instruction}:\n--------------------\n{expert_advice}"

            except Exception:
                print(traceback.format_exc())
                reply_message = "抱歉，助理目前有點忙線中，請稍後再試。\n(Maaf, asisten sedang sibuk, silakan coba lagi nanti.)"
    
    # --- 模式 B: 一般翻譯模式 (含祝福功能) ---
    else:
        try:
            detected = translator.detect(user_message)
            detected_lang = detected.lang
            
            target_text = ""
            
            if detected_lang in ['zh-TW', 'zh-CN']:
                # 中文 -> 印尼文 (AI 會自動加祝福)
                try:
                    target_text = ai_translate(user_message, 'zh-TW', 'id')
                except:
                    target_text = translator.translate(user_message, dest='id').text
                
                reply_message = (
                    f"🇹🇼 原文 (Asli):\n{user_message}\n"
                    f"--------------------\n"
                    f"🇮🇩 翻譯 (Terjemahan):\n{target_text}"
                )

            elif detected_lang == 'id':
                # 印尼文 -> 中文
                try:
                    target_text = ai_translate(user_message, 'id', 'zh-TW')
                except:
                    target_text = translator.translate(user_message, dest='zh-TW').text

                reply_message = (
                    f"🇮🇩 Asli (原文):\n{user_message}\n"
                    f"--------------------\n"
                    f"🇹🇼 Terjemahan (中文翻譯):\n{target_text}"
                )

            elif detected_lang == 'en':
                target_text = translator.translate(user_message, dest='id').text
                reply_message = (
                    f"🇬🇧 Original (Asli):\n{user_message}\n"
                    f"--------------------\n"
                    f"🇮🇩 Translation (Terjemahan):\n{target_text}"
                )
                
        except Exception:
            print(traceback.format_exc())
            return

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