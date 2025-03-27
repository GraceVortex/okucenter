#!/usr/bin/env python
"""
Script to ensure required directories exist on deployment.
This is particularly useful for Railway deployment where the container might not have
all the necessary directories created automatically.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def ensure_directories():
    """Ensure all required directories exist."""
    directories = [
        BASE_DIR / 'static',
        BASE_DIR / 'staticfiles',
        BASE_DIR / 'media',
        BASE_DIR / 'logs',
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            print(f"Creating directory: {directory}")
            os.makedirs(directory, exist_ok=True)
        else:
            print(f"Directory already exists: {directory}")

if __name__ == "__main__":
    print("Ensuring all required directories exist...")
    ensure_directories()
    print("Directory check complete.")
