from django.contrib import admin
from .models import Asset, Maintenance, Incident

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    # Updated to match the fields in your new models.py
    list_display = ('assets_id', 'assets_name', 'assets_type', 'location', 'status', 'date_added') 
    
    # Updated sidebar filters to use valid fields
    list_filter = ('assets_type', 'status', 'location')
    
    # Search box now looks through ID and name
    search_fields = ('assets_id', 'assets_name', 'location')

@admin.register(Maintenance)
class MaintenanceAdmin(admin.ModelAdmin):
    list_display = ('asset', 'maintenance_type', 'date', 'status')
    list_filter = ('status', 'date')
    date_hierarchy = 'date' 

@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    # Note: Ensure Incident model has a 'title' field as defined in your models.py
    list_display = ('title', 'severity', 'status', 'date')
    list_filter = ('severity', 'status', 'date')
    ordering = ('-severity',)