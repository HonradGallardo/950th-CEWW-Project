from django.urls import path, include
from rest_framework.routers import DefaultRouter

from CEWWproject import settings
from . import views
# Matches lowercase 'api' folder and singular 'viewset.py' file
from .api.viewset import TicketViewSet 

app_name = 'tickets'

router = DefaultRouter()
router.register(r'support-api', TicketViewSet, basename='api-support')

urlpatterns = [
    path('submit/', views.submit_ticket, name='submit_ticket'),
    path('manage/', views.admin_ticket_dashboard, name='admin_tickets'),
    path('detail/<int:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    path('api/', include(router.urls)),
]

