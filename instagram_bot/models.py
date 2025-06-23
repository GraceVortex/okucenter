from django.db import models
from django.utils import timezone


class InstagramClient(models.Model):
    """Model to store Instagram user information"""
    instagram_id = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Instagram Client: {self.instagram_id}"
    
    class Meta:
        verbose_name = "Instagram Client"
        verbose_name_plural = "Instagram Clients"


class InstagramMessage(models.Model):
    """Model to store conversation history"""
    CLIENT = 'client'
    BOT = 'bot'
    SENDER_CHOICES = [
        (CLIENT, 'Client'),
        (BOT, 'Bot'),
    ]
    
    client = models.ForeignKey(InstagramClient, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=20, choices=SENDER_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.sender.capitalize()} message at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
    class Meta:
        verbose_name = "Instagram Message"
        verbose_name_plural = "Instagram Messages"
        ordering = ['timestamp']


class SystemPrompt(models.Model):
    """Model to store and manage system prompt for the bot"""
    content = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        """Ensure only one active system prompt exists"""
        if self.is_active:
            SystemPrompt.objects.filter(is_active=True).update(is_active=False)
        super().save(*args, **kwargs)
    
    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"System Prompt ({status}) - {self.created_at.strftime('%Y-%m-%d')}"
    
    class Meta:
        verbose_name = "System Prompt"
        verbose_name_plural = "System Prompts"
