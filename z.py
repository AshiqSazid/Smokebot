import threading
import time
import pyttsx3
import speech_recognition as sr
import queue
import pandas as pd
import os
import json
import openai
from datetime import datetime
from vosk import Model, KaldiRecognizer
import pyaudio

CSV_FILE = "product_data.csv"
LOG_FILE = "voice_conversations.xlsx"
JSONL_FILE = "training_data.jsonl"
FINE_TUNED_MODEL = "ft:gpt-3.5-turbo-0125:podlove::BUkq9tMJ"  

recognizer = sr.Recognizer()
voice_latest_question = queue.Queue()
interrupt_flag = threading.Event()
speaking_thread = None
processing_thread = None
speaking_in_progress = False
processing_in_progress = False

# --- TTS ---
def speak(text):
    global speaking_in_progress
    speaking_in_progress = True
    try:
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print(f"TTS error: {e}")
    finally:
        speaking_in_progress = False

def speak_async(text):
    global speaking_thread
    if speaking_thread and speaking_thread.is_alive():
        speaking_thread.join()
    speaking_thread = threading.Thread(target=speak, args=(text,))
    speaking_thread.start()

# --- Mic ---
def get_default_microphone():
    mic_list = sr.Microphone.list_microphone_names()
    for i, mic_name in enumerate(mic_list):
        if "default" in mic_name.lower() or "microphone" in mic_name.lower():
            return sr.Microphone(device_index=i)
    return sr.Microphone(device_index=0)

def listen(timeout=10, phrase_time_limit=20):
    try:
        with get_default_microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1.0)
            recognizer.pause_threshold = 1.0
            print("🎤 Listening...")
            time.sleep(0.5)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            query = recognizer.recognize_google(audio)
            print(f"🗣️ You said: {query}")
            return query
    except sr.UnknownValueError:
        print("⚠️ Could not understand audio.")
    except sr.RequestError as e:
        print(f"Speech API error: {e}")
    except Exception as e:
        print(f"Listen error: {e}")
    return None

# --- CSV Handling ---
def load_product_data(filepath=CSV_FILE):
    df = pd.read_csv(filepath)
    required_cols = {'name', 'category', 'price', 'description'}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"❌ CSV missing required columns. Found: {list(df.columns)}")
    return df

# --- Fine-Tuned Model Query ---
def ask_finetuned_llm(prompt):
    try:
        openai.api_key = os.getenv("OPENAI_API_KEY")
        response = openai.ChatCompletion.create(
            model=FINE_TUNED_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        print(f"LLM error: {e}")
        return "Sorry, I'm having trouble accessing my knowledge base."

# --- CSV + LLM Fallback ---
def query_csv_with_llm_fallback(question, product_file=CSV_FILE):
    try:
        df = load_product_data(product_file)
        query = question.lower().strip()
        matches = []
        for _, row in df.iterrows():
            name = str(row['name']).lower()
            desc = str(row['description']).lower()
            if any(word in name or word in desc for word in query.split()):
                matches.append(row)

        if not matches:
            return ask_finetuned_llm(question)

        top_matches = matches[:3]
        response = ""
        for row in top_matches:
            response += f"The {row['name']} is available for ${row['price']}. It’s a {row['description']}.\n"
        return response.strip()

    except Exception as e:
        print(f"CSV error: {e}")
        return ask_finetuned_llm(question)

# --- Logging ---
def log_conversation_to_excel(question, response):
    entry = {
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "User_Question": question,
        "Bot_Response": response
    }
    if os.path.exists(LOG_FILE):
        df = pd.read_excel(LOG_FILE)
    else:
        df = pd.DataFrame(columns=["Timestamp", "User_Question", "Bot_Response"])
    df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
    df.to_excel(LOG_FILE, index=False)

def convert_excel_to_jsonl():
    try:
        if not os.path.exists(LOG_FILE):
            return
        df = pd.read_excel(LOG_FILE)
        with open(JSONL_FILE, 'w', encoding='utf-8') as f:
            for _, row in df.iterrows():
                data = {
                    "messages": [
                        {"role": "user", "content": str(row["User_Question"])},
                        {"role": "assistant", "content": str(row["Bot_Response"])}
                    ]
                }
                f.write(json.dumps(data) + "\n")
        print(f"✅ Converted logs to {JSONL_FILE}")
    except Exception as e:
        print(f"❌ JSONL conversion failed: {e}")

# --- Main Logic ---
def process_voice_question():
    global processing_in_progress
    processing_in_progress = True
    while not voice_latest_question.empty():
        question = voice_latest_question.get()
        answer = query_csv_with_llm_fallback(question)
        log_conversation_to_excel(question, answer)
        convert_excel_to_jsonl()
        if not interrupt_flag.is_set():
            speak_async(answer)
    processing_in_progress = False

def trigger_assistant():
    speak_async("Hi there! Ask me anything about vapes, CBD, cigars, or accessories. Say 'exit','bye' to quit.")
    query = listen()
    if query:
        if query.lower() in ['exit', 'quit', 'stop','bye']:
            speak_async("Goodbye!")
            os._exit(0)
        interrupt_flag.set()
        time.sleep(0.3)
        with voice_latest_question.mutex:
            voice_latest_question.queue.clear()
        voice_latest_question.put(query)
        interrupt_flag.clear()
        global processing_thread
        if processing_thread is None or not processing_thread.is_alive():
            processing_thread = threading.Thread(target=process_voice_question)
            processing_thread.start()
    else:
        speak_async("Sorry, I didn’t catch that.")

def conversation_loop():
    global processing_thread
    while True:
        query = listen()
        if query:
            if query.lower() in ['exit', 'quit', 'stop','bye']:
                speak_async("Goodbye!")
                break
            interrupt_flag.set()
            time.sleep(0.3)
            with voice_latest_question.mutex:
                voice_latest_question.queue.clear()
            voice_latest_question.put(query)
            interrupt_flag.clear()
            if processing_thread is None or not processing_thread.is_alive():
                processing_thread = threading.Thread(target=process_voice_question)
                processing_thread.start()
        else:
            speak_async("Sorry, I didn’t catch that.")

def vosk_hotword_loop():
    speak_async("Say 'Hey' to wake me up.")
    model = Model("model")
    rec = KaldiRecognizer(model, 16000)
    mic = pyaudio.PyAudio().open(format=pyaudio.paInt16, channels=1,
                                 rate=16000, input=True, frames_per_buffer=8192)
    mic.start_stream()

    print("🎙️ Waiting for hotword 'hey'...")
    while True:
        data = mic.read(4096, exception_on_overflow=False)
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text = result.get("text", "")
            print("Heard:", text)
            if "hey" in text.lower():
                trigger_assistant()
                break

    conversation_loop()

if __name__ == "__main__":
    vosk_hotword_loop()