# views.py

import asyncio
import aiohttp
import threading
import queue
import time
import requests
import speech_recognition as sr
import pyttsx3
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.views.generic.base import TemplateView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from .models import Conversation, ProductReviews
from .forms import RegisterForm

# --- Groq API Setup ---
GROQ_API_KEY = "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"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama3-70b-8192"

# --- Shared State ---
latest_question_lock = threading.Lock()
latest_question_text = None
latest_question_time = 0
recognizer = sr.Recognizer()
voice_latest_question = queue.Queue()
interrupt_flag = threading.Event()
speaking_thread = None
processing_thread = None
speaking_in_progress = False
processing_in_progress = False

# ==================== Django Web Views ====================

class HomePage(TemplateView):
    template_name = "home/index.html"

@csrf_exempt
@csrf_exempt
def voicebot_post(request):
    if request.method == "POST":
        text = request.POST.get("text")
        if text:
            # --- Now make actual Groq API call ---
            try:
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": text}
                    ],
                    "temperature": 0.6,
                    "max_tokens": 512
                }
                response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=10)
                response.raise_for_status()
                data = response.json()
                bot_reply = data["choices"][0]["message"]["content"]
                return JsonResponse({"reply": bot_reply})
            except Exception as e:
                print(f"Groq API error: {e}")
                return JsonResponse({"error": "Failed to fetch reply"}, status=500)
        else:
            return JsonResponse({"error": "No text provided"}, status=400)
    else:
        return JsonResponse({"error": "Only POST requests are accepted"}, status=405)

def home(request):
    return HttpResponse("Welcome to SmokeBot 🚀")

async def query_groq_async(question: str) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful voice assistant. Keep your replies short, casual, and natural. Avoid mentioning that you are an AI."},
            {"role": "user", "content": question}
        ],
        "temperature": 0.6,
        "max_tokens": 512
    }
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(GROQ_API_URL, headers=headers, json=payload) as response:
            data = await response.json()
            return data["choices"][0]["message"]["content"]

def analyze_sentiment(text: str) -> str:
    score = SentimentIntensityAnalyzer().polarity_scores(text)["compound"]
    if score >= 0.05:
        return "positive"
    if score <= -0.05:
        return "negative"
    return "neutral"

@login_required
def text_generator(request):
    global latest_question_text, latest_question_time

    chat_history = Conversation.objects.filter(user=request.user).order_by("-timestamp")[:10]

    if request.method == "POST":
        user_input = request.POST.get("text")
        if user_input:
            with latest_question_lock:
                latest_question_text = user_input
                latest_question_time = time.time()

            time.sleep(0.8)
            with latest_question_lock:
                if user_input != latest_question_text:
                    return redirect("chat")

            bot_reply = asyncio.run(query_groq_async(latest_question_text))
            sentiment = analyze_sentiment(user_input)

            if sentiment == "positive":
                bot_reply += "\n\nYay! 😊 You're in a great mood!"
            elif sentiment == "negative":
                bot_reply += "\n\nI'm sorry to hear that. 😞 How can I help?"
            else:
                bot_reply += "\n\nGot it! Let me know if you need anything."

            Conversation.objects.create(
                user=request.user,
                user_input=user_input,
                bot_response=bot_reply
            )
            chat_history = Conversation.objects.filter(user=request.user).order_by("-timestamp")[:10]

    return render(request, "chat.html", {"chat_history": chat_history})

def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("chat")
    else:
        form = RegisterForm()
    return render(request, "register.html", {"form": form})

def custom_login(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect("chat")
    else:
        form = AuthenticationForm()
    return render(request, "login.html", {"form": form})

def custom_logout(request):
    auth_logout(request)
    return redirect('home')

# ==================== VoiceBot Functions ====================

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

def listen(timeout=10, phrase_time_limit=10):
    try:
        mic_list = sr.Microphone.list_microphone_names()
        if not mic_list:
            raise RuntimeError("❌ No input microphone found.")
        with sr.Microphone(device_index=0) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print("🎤 Listening...")
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

def query_groq_sync(question):
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": question}
            ],
            "temperature": 0.6,
            "max_tokens": 512
        }
        response = requests.post(GROQ_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "Sorry, no valid response received.")
    except Exception as e:
        print(f"Groq API error: {e}")
        return "Sorry, I encountered an error."

def process_voice_question():
    global processing_in_progress
    processing_in_progress = True
    while not voice_latest_question.empty():
        question = voice_latest_question.get()
        answer = query_groq_sync(question)
        if not interrupt_flag.is_set():
            speak_async(answer)
    processing_in_progress = False

def listen_loop():
    speak_async("VoiceBot is ready! Say 'exit' to quit.")
    while True:
        query = listen()
        if query:
            if query.lower() in ['exit', 'quit', 'stop']:
                speak_async("Goodbye!")
                break
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
            speak_async("Sorry, I didn't catch that. Please try again.")

# ==================== Product Reviews ====================

class CreateReview(CreateView):
    model = ProductReviews
    fields = ['product', 'author', 'title', 'content', 'rating']
    template_name = 'home/create_review.html'
    success_url = '/'

class EditReview(UpdateView):
    model = ProductReviews
    fields = ['title', 'content', 'rating']
    template_name = 'home/edit_review.html'
    success_url = '/'

class DeleteReview(DeleteView):
    model = ProductReviews
    template_name = 'home/delete_review.html'
    success_url = reverse_lazy('home')
