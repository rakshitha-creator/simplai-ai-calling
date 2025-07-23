
from flask import Flask, request, Response, send_from_directory
from twilio.twiml.voice_response import VoiceResponse, Gather
import google.generativeai as genai
import requests
import uuid
import os

app = Flask(__name__)

# ========== CONFIG ==========
import os
GEMINI_API_KEY = os.getenv("AIzaSyCKEUlTtETH10agbV34-Xpxaf7zlBcQHJg")
ELEVENLABS_API_KEY = os.getenv("sk_a5ac972b122a92e70df049a3c839ec1aee1f53e6eb24b3ae")
VOICE_ID = "zT03pEAEi0VHKciJODfn"
BASE_URL = "https://simplai-ai-calling.onrender.com"
AUDIO_DIR = os.path.join(os.getcwd(), "audio_files")
os.makedirs(AUDIO_DIR, exist_ok=True)
genai.configure(api_key=GEMINI_API_KEY)

IM_CONTEXT = """IM Solutions is a digital agency offering SEO, paid ads, branding, social media, ORM, and web design."""

# ========== AUDIO SYNTHESIS ==========
def synthesize_11labs_audio(text, filename):
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}
        }
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            file_path = os.path.join(AUDIO_DIR, filename)
            with open(file_path, "wb") as f:
                f.write(response.content)
            print("[✓] Audio saved:", file_path)
            return file_path
        else:
            print("[X] 11Labs error:", response.status_code, response.text)
    except Exception as e:
        print("[X] 11Labs exception:", e)
    return None

# ========== ROUTES ==========
@app.route("/")
def home():
    return "✅ Flask server for Gemini + 11Labs is running."

@app.route("/voice", methods=["GET", "POST"])
def voice():
    user_name = request.args.get("name", "there").strip().title()
    welcome_text = f"Hello {user_name}, welcome to IM Solutions. How may I help you today?"
    filename = f"welcome_{uuid.uuid4().hex}.mp3"
    path = synthesize_11labs_audio(welcome_text, filename)

    response = VoiceResponse()
    gather = Gather(input="speech", action="/response", method="POST", language="en-IN", speech_timeout="auto")

    if path and os.path.exists(path):
        url = f"{BASE_URL}/audio/{filename}"
        print("[✓] Returning welcome audio:", url)
        gather.play(url)
    else:
        print("[!] Fallback to Say: audio file not found.")
        gather.say(welcome_text, voice="Polly.Aditi", language="en-IN")

    response.append(gather)
    return Response(str(response), mimetype="text/xml")

@app.route("/response", methods=["POST"])
def handle_response():
    user_input = request.form.get("SpeechResult", "").strip()
    print("[User]:", user_input)
    response = VoiceResponse()

    if not user_input:
        gather = Gather(input="speech", action="/response", method="POST", language="en-IN", speech_timeout="auto")
        gather.say("Sorry, I didn’t catch that. Please say that again.", voice="Polly.Aditi", language="en-IN")
        response.append(gather)
        return Response(str(response), mimetype="text/xml")

    if any(word in user_input.lower() for word in ["bye", "thank", "no", "nothing"]):
        goodbye_text = "Thank you for contacting IM Solutions. Have a great day!"
        filename = f"goodbye_{uuid.uuid4().hex}.mp3"
        path = synthesize_11labs_audio(goodbye_text, filename)
        if path:
            response.play(f"{BASE_URL}/audio/{filename}")
        else:
            response.say(goodbye_text, voice="Polly.Aditi", language="en-IN")
        response.hangup()
        return Response(str(response), mimetype="text/xml")

    prompt = f"""{IM_CONTEXT}

User: {user_input}

Reply briefly in friendly Indian English, max 2 sentences."""

    try:
        model = genai.GenerativeModel("models/gemini-1.5-flash-latest")
        result = model.generate_content(prompt)
        ai_reply = result.text.strip()
    except Exception as e:
        print("[X] Gemini error:", e)
        ai_reply = "Sorry, I'm unable to respond right now."

    print("[AI]:", ai_reply)

    filename = f"reply_{uuid.uuid4().hex}.mp3"
    path = synthesize_11labs_audio(ai_reply, filename)

    if path:
        response.play(f"{BASE_URL}/audio/{filename}")
    else:
        response.say(ai_reply, voice="Polly.Aditi", language="en-IN")

    gather = Gather(input="speech", action="/response", method="POST", language="en-IN", speech_timeout="auto")
    gather.say("Do you have any other questions?", voice="Polly.Aditi", language="en-IN")
    response.append(gather)
    return Response(str(response), mimetype="text/xml")

@app.route("/audio/<filename>")
def serve_audio(filename):
    full_path = os.path.join(AUDIO_DIR, filename)
    print("[✓] Serving:", full_path)
    if os.path.exists(full_path):
        return send_from_directory(AUDIO_DIR, filename, mimetype="audio/mpeg")
    return "Audio not found", 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
