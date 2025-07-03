from dotenv import load_dotenv
import os

load_dotenv()
class Config:
    MONGO_URI = os.getenv('MONGO_URI')
    
    GOOGLE_APPLICATION_CREDENTIALS_JSON = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
    
    FIREBASE_DATABASE_URL = os.getenv('FIREBASE_DATABASE_URL')