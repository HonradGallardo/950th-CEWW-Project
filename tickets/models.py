from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

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
    last_technician = models.CharField(max_length=150, blank=True, null=True) 

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


class TicketMessage(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    attachment = models.FileField(upload_to='chat_attachments/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    recipient = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='received_messages'
    )
    message = models.TextField()
    is_group_chat = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        recipient_name = self.recipient.username if self.recipient else "Everyone"
        return f"From {self.sender.username} to {recipient_name} on Ticket #{self.ticket.id}"
    
class TicketAttachment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='all_attachments')
    
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


# ==========================================
# 🚨 AUTOMATIC NOTIFICATION SIGNALS 🚨
# ==========================================

@receiver(post_save, sender=Ticket)
def notify_new_ticket(sender, instance, created, **kwargs):
    """Triggers automatically when a new Ticket is saved to the database"""
    if created:
        from core.models import Notification # Local import to prevent circular dependencies
        
        # 1. Notify the user who submitted the ticket
        if instance.user and instance.user.username != 'PublicGuest':
            Notification.objects.create(
                recipient=instance.user,
                message=f"Support ticket submitted successfully: {instance.subject}"
            )
            
        # 2. Notify all Admins that a new ticket arrived
        admin_users = User.objects.filter(groups__name='Admin')
        for admin in admin_users:
            if admin != instance.user:  # Don't notify the admin if they submitted it themselves
                Notification.objects.create(
                    recipient=admin,
                    message=f"New support ticket requires review: {instance.subject}"
                )

@receiver(post_save, sender=TicketMessage)
def notify_new_ticket_message(sender, instance, created, **kwargs):
    """Triggers automatically when a new message or reply is sent in a ticket"""
    if created:
        from core.models import Notification # Local import
        
        ticket = instance.ticket
        sender_user = instance.sender
        recipient_user = instance.recipient

        # Scenario A: An explicit recipient was selected (Direct message)
        if recipient_user and recipient_user != sender_user:
            Notification.objects.create(
                recipient=recipient_user,
                message=f"New ticket message from {sender_user.username}"
            )
            
        # Scenario B: No explicit recipient, but the ticket is assigned to a technician
        elif ticket.technician and ticket.technician != sender_user:
            Notification.objects.create(
                recipient=ticket.technician,
                message=f"New reply on ticket #{ticket.id} from {sender_user.username}"
            )
            
        # Scenario C: A technician/admin replied, so notify the ticket owner
        elif ticket.user and ticket.user != sender_user:
            Notification.objects.create(
                recipient=ticket.user,
                message=f"New update on your support ticket #{ticket.id}"
            )