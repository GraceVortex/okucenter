import os
from dotenv import load_dotenv
from instagram_webhook import app
from database import init_db

# Load environment variables
load_dotenv()

# Initialize database
init_db()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 3000))
    print(f"Starting Instagram chatbot on port {port}...")
    print("Press Ctrl+C to exit")
    app.run(host='0.0.0.0', port=port, debug=False)
