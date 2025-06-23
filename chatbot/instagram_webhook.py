import os
import json
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from database import save_message, get_conversation_history, init_db
from openai_client import generate_response

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Initialize database
init_db()

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """
    Handle the webhook verification from Instagram
    This is required when setting up the webhook
    """
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode and token:
        # Check if the token matches our verification token
        if mode == 'subscribe' and token == os.getenv('INSTAGRAM_VERIFY_TOKEN'):
            print("Webhook verified!")
            return challenge
        else:
            return jsonify({"error": "Verification failed"}), 403
    else:
        return jsonify({"error": "Missing parameters"}), 400

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """
    Handle incoming webhook events from Instagram
    """
    data = request.json
    
    # Check if this is a message event
    if data.get('object') == 'instagram':
        for entry in data.get('entry', []):
            for messaging in entry.get('messaging', []):
                sender_id = messaging.get('sender', {}).get('id')
                message_text = messaging.get('message', {}).get('text')
                
                if sender_id and message_text:
                    # Save client message to database
                    save_message(sender_id, message_text, 'client')
                    
                    # Get conversation history
                    client_messages, bot_messages = get_conversation_history(sender_id)
                    
                    # Generate response using OpenAI
                    response_text = generate_response(client_messages, bot_messages)
                    
                    # Save bot response to database
                    save_message(sender_id, response_text, 'bot')
                    
                    # Send response back to Instagram
                    send_message(sender_id, response_text)
    
    return jsonify({"status": "ok"})

def send_message(recipient_id, message_text):
    """
    Send a message to the Instagram user
    
    Args:
        recipient_id: Instagram user ID
        message_text: Message to send
    """
    url = f"https://graph.facebook.com/v13.0/me/messages"
    params = {
        "access_token": os.getenv('INSTAGRAM_ACCESS_TOKEN')
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

if __name__ == '__main__':
    port = int(os.getenv('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
