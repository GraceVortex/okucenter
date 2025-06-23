import os
from dotenv import load_dotenv
from database import init_db, save_message, get_conversation_history
from openai_client import generate_response

# Load environment variables
load_dotenv()

# Initialize database
init_db()

def test_bot():
    """
    Simple test function to check if the bot works
    """
    # Simulated Instagram user ID
    test_user_id = "test_user_123"
    
    # Test messages
    test_messages = [
        "Привет! Расскажи о вашем образовательном центре.",
        "Какие предметы вы преподаете?",
        "Сколько стоит обучение?",
        "Как записаться на пробное занятие?"
    ]
    
    print("=== Testing Chat Bot ===\n")
    
    for message in test_messages:
        print(f"User: {message}")
        
        # Save client message to database
        save_message(test_user_id, message, 'client')
        
        # Get conversation history
        client_messages, bot_messages = get_conversation_history(test_user_id)
        
        # Generate response using OpenAI
        response_text = generate_response(client_messages, bot_messages)
        
        # Save bot response to database
        save_message(test_user_id, response_text, 'bot')
        
        print(f"Bot: {response_text}\n")
        print("-" * 50)

if __name__ == '__main__':
    test_bot()
