import os
import json
import requests
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.conf import settings
from .models import InstagramClient, InstagramMessage, SystemPrompt
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)


def get_system_prompt():
    """Get the active system prompt from the database"""
    try:
        prompt = SystemPrompt.objects.filter(is_active=True).first()
        if prompt:
            return prompt.content
        # If no active prompt, use default from chatbot directory
        with open(os.path.join(settings.BASE_DIR, 'chatbot', 'systemprompt.txt'), 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"Error getting system prompt: {e}")
        return "You are a helpful assistant for an educational center."


def get_conversation_history(instagram_id, limit=10):
    """Get conversation history for a specific client"""
    try:
        # Get or create client
        client, created = InstagramClient.objects.get_or_create(instagram_id=instagram_id)
        
        # Get client and bot messages
        client_messages = InstagramMessage.objects.filter(
            client=client, sender=InstagramMessage.CLIENT
        ).order_by('-timestamp')[:limit]
        
        bot_messages = InstagramMessage.objects.filter(
            client=client, sender=InstagramMessage.BOT
        ).order_by('-timestamp')[:limit]
        
        # Convert to lists and reverse for chronological order
        client_messages = list(client_messages)
        client_messages.reverse()
        
        bot_messages = list(bot_messages)
        bot_messages.reverse()
        
        return client_messages, bot_messages
    except Exception as e:
        print(f"Error getting conversation history: {e}")
        return [], []


def save_message(instagram_id, content, sender):
    """Save a message to the database"""
    try:
        # Get or create client
        client, created = InstagramClient.objects.get_or_create(instagram_id=instagram_id)
        
        # Create message
        InstagramMessage.objects.create(
            client=client,
            sender=sender,
            content=content
        )
    except Exception as e:
        print(f"Error saving message: {e}")


def generate_response(client_messages, bot_messages):
    """Generate a response using OpenAI API"""
    system_prompt = get_system_prompt()
    
    # Create conversation history for OpenAI
    messages = [{"role": "system", "content": system_prompt}]
    
    # Interleave client and bot messages to create conversation history
    all_messages = []
    for msg in client_messages:
        all_messages.append({"msg": msg, "is_client": True})
    for msg in bot_messages:
        all_messages.append({"msg": msg, "is_client": False})
    
    # Sort by timestamp
    all_messages.sort(key=lambda x: x["msg"].timestamp)
    
    # Add to messages list
    for item in all_messages:
        if item["is_client"]:
            messages.append({"role": "user", "content": item["msg"].content})
        else:
            messages.append({"role": "assistant", "content": item["msg"].content})
    
    try:
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        
        # Extract and return the response text
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return "Извините, у нас возникли технические проблемы. Пожалуйста, попробуйте позже."


def send_message(recipient_id, message_text):
    """Send a message to the Instagram user"""
    url = f"https://graph.facebook.com/v13.0/me/messages"
    params = {
        "access_token": settings.INSTAGRAM_ACCESS_TOKEN
    }
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    
    try:
        response = requests.post(url, params=params, json=data)
        if response.status_code != 200:
            print(f"Failed to send message: {response.text}")
    except Exception as e:
        print(f"Error sending message: {e}")


@csrf_exempt
def instagram_webhook(request):
    """Handle Instagram webhook - both verification (GET) and message handling (POST)"""
    if request.method == 'GET':
        # Handle webhook verification
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        if mode and token:
            # Check if the token matches our verification token
            if mode == 'subscribe' and token == settings.INSTAGRAM_VERIFY_TOKEN:
                print("Webhook verified!")
                return HttpResponse(challenge)
            else:
                return JsonResponse({"error": "Verification failed"}, status=403)
        else:
            return JsonResponse({"error": "Missing parameters"}, status=400)
    
    elif request.method == 'POST':
        # Handle incoming webhook events from Instagram
        try:
            data = json.loads(request.body.decode('utf-8'))
            
            # Check if this is a message event
            if data.get('object') == 'instagram':
                for entry in data.get('entry', []):
                    for messaging in entry.get('messaging', []):
                        sender_id = messaging.get('sender', {}).get('id')
                        message_text = messaging.get('message', {}).get('text')
                        
                        if sender_id and message_text:
                            # Save client message to database
                            save_message(sender_id, message_text, InstagramMessage.CLIENT)
                            
                            # Get conversation history
                            client_messages, bot_messages = get_conversation_history(sender_id)
                            
                            # Generate response using OpenAI
                            response_text = generate_response(client_messages, bot_messages)
                            
                            # Save bot response to database
                            save_message(sender_id, response_text, InstagramMessage.BOT)
                            
                            # Send response back to Instagram
                            send_message(sender_id, response_text)
            
            return JsonResponse({"status": "ok"})
        except Exception as e:
            print(f"Error handling webhook: {e}")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    
    # If not GET or POST, return method not allowed
    return JsonResponse({"error": "Method not allowed"}, status=405)
