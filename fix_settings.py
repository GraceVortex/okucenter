#!/usr/bin/env python
"""
Script to fix common deployment issues on Railway.
This script modifies the settings.py file to ensure compatibility with Railway's environment.
"""
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = BASE_DIR / 'okucenter' / 'settings.py'

def fix_static_url():
    """Ensure STATIC_URL has a trailing slash."""
    if not os.path.exists(SETTINGS_FILE):
        print(f"Error: Settings file not found at {SETTINGS_FILE}")
        return False
    
    with open(SETTINGS_FILE, 'r') as f:
        content = f.read()
    
    # Check if STATIC_URL is correctly defined with a trailing slash
    if "STATIC_URL = '/static/'" in content:
        print("STATIC_URL already has a trailing slash.")
        return True
    
    # Replace STATIC_URL without trailing slash
    new_content = re.sub(
        r"STATIC_URL\s*=\s*['\"]static/['\"]", 
        "STATIC_URL = '/static/'", 
        content
    )
    
    # Also replace any other variations
    new_content = re.sub(
        r"STATIC_URL\s*=\s*['\"]static['\"]", 
        "STATIC_URL = '/static/'", 
        new_content
    )
    
    if new_content != content:
        with open(SETTINGS_FILE, 'w') as f:
            f.write(new_content)
        print("Fixed STATIC_URL to include a trailing slash.")
        return True
    else:
        print("Could not find STATIC_URL pattern to replace. Manual inspection needed.")
        
        # Force set the correct STATIC_URL at the end of the file
        with open(SETTINGS_FILE, 'a') as f:
            f.write("\n\n# Forced override for Railway deployment\n")
            f.write("STATIC_URL = '/static/'\n")
        print("Appended correct STATIC_URL setting to the end of the file.")
        return True

if __name__ == "__main__":
    print("Fixing settings for Railway deployment...")
    fix_static_url()
    print("Settings fix complete.")
