from django.db import models
from django.conf import settings
from django.contrib.auth.models import User

class Ticket(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Resolved', 'Resolved'),
        ('Closed', 'Closed'),
    ]

    PRIORITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
    ]

    # The staff member currently handling the ticket
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='technician_tickets'
    )
    last_technician = models.CharField(max_length=150, blank=True, null=True) # Add this!

    subject = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Low')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    description = models.TextField()
    
    # The user who created the ticket
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='tickets'
    )

    # Standard timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Optional fields for file attachments
    attachment = models.FileField(upload_to='ticket_attachments/', null=True, blank=True)

    def __str__(self):
        return f"Ticket #{self.id} - {self.subject}"


# models.py

# models.py
class TicketMessage(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    attachment = models.FileField(upload_to='chat_attachments/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Add this field if it's missing or clashing
    recipient = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='received_messages'
    )
    message = models.TextField()
    is_group_chat = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        recipient_name = self.recipient.username if self.recipient else "Everyone"
        return f"From {self.sender.username} to {recipient_name} on Ticket #{self.ticket.id}"
    
class TicketAttachment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='all_attachments')
    
    # ADD THIS FIELD: Links the file to a specific message bubble
    message = models.ForeignKey(
        TicketMessage, 
        on_delete=models.CASCADE, 
        related_name='attachments', 
        null=True, 
        blank=True
    )
    
    file = models.FileField(upload_to='ticket_attachments/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"File for Ticket #{self.ticket.id} (Msg: {self.message_id or 'General'})"
