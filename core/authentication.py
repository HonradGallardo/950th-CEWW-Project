from rest_framework.authentication import TokenAuthentication
from rest_framework import exceptions
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

class ExpiringTokenAuthentication(TokenAuthentication):
    keyword = 'Bearer'
    
    def authenticate_credentials(self, key):
        model = self.get_model()
        try:
            token = model.objects.select_related('user').get(key=key)
        except model.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid token.')

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed('User inactive or deleted.')

        # Check if token is older than 30 minutes
        if timezone.now() > token.created + timedelta(minutes=30):
            token.delete()  # Manually delete the expired token
            raise exceptions.AuthenticationFailed('Token has expired.')

        token.created = timezone.now()
        token.save()

        return (token.user, token)