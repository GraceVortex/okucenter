from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create database engine
engine = create_engine(os.getenv('DATABASE_URL'))
Base = declarative_base()
Session = sessionmaker(bind=engine)

class Client(Base):
    """Client model to store Instagram user information"""
    __tablename__ = 'clients'
    
    id = Column(Integer, primary_key=True)
    instagram_id = Column(String(50), unique=True)
    messages = relationship("Message", back_populates="client")
    
    def __repr__(self):
        return f"<Client(instagram_id='{self.instagram_id}')>"

class Message(Base):
    """Message model to store conversation history"""
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'))
    sender = Column(String(20))  # 'client' or 'bot'
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    client = relationship("Client", back_populates="messages")
    
    def __repr__(self):
        return f"<Message(sender='{self.sender}', timestamp='{self.timestamp}')>"

def init_db():
    """Initialize the database by creating all tables"""
    Base.metadata.create_all(engine)

def get_session():
    """Get a new database session"""
    return Session()

def get_conversation_history(instagram_id, limit=10):
    """
    Get the conversation history for a specific client
    Returns two lists: client_messages and bot_messages (up to 'limit' messages each)
    """
    session = get_session()
    
    # Get or create client
    client = session.query(Client).filter_by(instagram_id=instagram_id).first()
    if not client:
        client = Client(instagram_id=instagram_id)
        session.add(client)
        session.commit()
    
    # Get client messages
    client_messages = (session.query(Message)
                      .filter_by(client_id=client.id, sender='client')
                      .order_by(Message.timestamp.desc())
                      .limit(limit)
                      .all())
    
    # Get bot messages
    bot_messages = (session.query(Message)
                   .filter_by(client_id=client.id, sender='bot')
                   .order_by(Message.timestamp.desc())
                   .limit(limit)
                   .all())
    
    session.close()
    
    # Reverse to get chronological order
    client_messages.reverse()
    bot_messages.reverse()
    
    return client_messages, bot_messages

def save_message(instagram_id, content, sender):
    """Save a message to the database"""
    session = get_session()
    
    # Get or create client
    client = session.query(Client).filter_by(instagram_id=instagram_id).first()
    if not client:
        client = Client(instagram_id=instagram_id)
        session.add(client)
        session.commit()
    
    # Create and save message
    message = Message(
        client_id=client.id,
        sender=sender,
        content=content
    )
    session.add(message)
    session.commit()
    session.close()
