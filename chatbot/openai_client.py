import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def get_system_prompt():
    """Read system prompt from file"""
    with open('systemprompt.txt', 'r', encoding='utf-8') as file:
        return file.read()

def generate_response(client_messages, bot_messages):
    """
    Generate a response using OpenAI API
    
    Args:
        client_messages: List of Message objects from client
        bot_messages: List of Message objects from bot
    
    Returns:
        str: Generated response text
    """
    system_prompt = get_system_prompt()
    
    # Create conversation history for OpenAI
    messages = [{"role": "system", "content": system_prompt}]
    
    # Interleave client and bot messages to create conversation history
    # We need to align them by timestamp
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
