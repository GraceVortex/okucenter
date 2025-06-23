import os
from django.core.management.base import BaseCommand
from django.conf import settings
from instagram_bot.models import SystemPrompt


class Command(BaseCommand):
    help = 'Import system prompt from chatbot directory'

    def handle(self, *args, **options):
        try:
            # Path to the system prompt file
            prompt_file_path = os.path.join(settings.BASE_DIR, 'chatbot', 'systemprompt.txt')
            
            # Check if file exists
            if not os.path.exists(prompt_file_path):
                self.stdout.write(self.style.ERROR(f'System prompt file not found at {prompt_file_path}'))
                return
            
            # Read the system prompt content
            with open(prompt_file_path, 'r', encoding='utf-8') as file:
                prompt_content = file.read()
            
            # Create a new system prompt
            system_prompt = SystemPrompt(
                content=prompt_content,
                is_active=True
            )
            system_prompt.save()
            
            self.stdout.write(self.style.SUCCESS('Successfully imported system prompt'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error importing system prompt: {e}'))
