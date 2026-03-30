from django.urls import path, include
from rest_framework.routers import DefaultRouter

from CEWWproject import settings
from . import views
from .api import views as api_views 
from .api.viewset import TicketViewSet 

app_name = 'tickets'

router = DefaultRouter()
router.register(r'support-api', TicketViewSet, basename='api-support')

urlpatterns = [
    path('submit/', views.submit_ticket, name='submit_ticket'),
    path('manage/', views.admin_ticket_dashboard, name='admin_tickets'),
    path('detail/<int:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    path('api/', include(router.urls)),
    
    # <--- FIX THIS LINE: Change views.track_ticket to api_views.track_ticket
    path('api/track/', api_views.track_ticket, name='track_ticket'), 
]