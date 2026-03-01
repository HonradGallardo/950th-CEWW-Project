def unread_notifications_count(request):
    if request.user.is_authenticated:
        count = request.user.notifications.filter(is_read=False).count()
        return {'unread_count': count}
    return {'unread_count': 0}

def notifications_processor(request):
    if request.user.is_authenticated:
        # This fetches notifications for the CURRENT user, 
        # whoever that may be (Admin, Commander, or Personnel)
        notifications = request.user.notifications.all().order_by('-created_at')[:5]
        unread_count = request.user.notifications.filter(is_read=False).count()
        return {
            'notifications': notifications,
            'unread_count': unread_count
        }
    return {}