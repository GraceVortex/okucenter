import os
from dotenv import load_dotenv
from database import init_db, save_message, get_conversation_history
from openai_client import generate_response

# Load environment variables
load_dotenv()

# Initialize database
init_db()

def simulate_conversation(instagram_id, message_text):
    """
    Simulate a conversation with the bot
    
    Args:
        instagram_id: Simulated Instagram user ID
        message_text: Message from the user
    """
    print(f"\nUser: {message_text}")
    
    # Save client message to database
    save_message(instagram_id, message_text, 'client')
    
    # Get conversation history
    client_messages, bot_messages = get_conversation_history(instagram_id)
    
    # Generate response using OpenAI
    response_text = generate_response(client_messages, bot_messages)
    
    # Save bot response to database
    save_message(instagram_id, response_text, 'bot')
    
    print(f"Bot: {response_text}")
    return response_text

if __name__ == '__main__':
    # Simulated Instagram user ID
    test_user_id = "test_user_123"
    
    print("=== Testing Chat Bot ===")
    print("Type a message or 'exit' to quit")
    
    while True:
        user_input = input("\nEnter message: ")
        if user_input.lower() == 'exit':
            break
        
        simulate_conversation(test_user_id, user_input)
