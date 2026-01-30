from django.contrib import admin
from .models import Asset, Maintenance, Incident

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    # Columns to show in the list view
    list_display = ('name', 'asset_type', 'assigned_to') 
    # Sidebar filters
    list_filter = ('asset_type', 'assigned_to')
    # Search box for finding specific hardware
    search_fields = ('name',)

@admin.register(Maintenance)
class MaintenanceAdmin(admin.ModelAdmin):
    list_display = ('asset', 'maintenance_type', 'date', 'status')
    list_filter = ('status', 'date')
    date_hierarchy = 'date' # Adds a date navigation bar at the top

@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ('title', 'severity', 'status', 'date')
    list_filter = ('severity', 'status', 'date')
    # Color-code or organize by severity in the admin
    ordering = ('-severity',)