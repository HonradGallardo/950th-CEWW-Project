from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewset import TicketViewSet  # Ensure this is singular 'viewset' per your sidebar

app_name = 'api'

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r'support-api', TicketViewSet, basename='ticket')

urlpatterns = [
    # This provides:
    # GET/POST /tickets/api/support-api/
    # GET/PUT/DELETE /tickets/api/support-api/<pk>/
    # GET /tickets/api/support-api/<pk>/chat_thread/
    # POST /tickets/api/support-api/<pk>/send_reply/
    # POST /tickets/api/support-api/<pk>/update_technical_details/
    path('', include(router.urls)),
]

