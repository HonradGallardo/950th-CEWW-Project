from rest_framework import serializers
from .models import Asset, Maintenance, Incident

class AssetSerializer(serializers.ModelSerializer):
    # Grabs the actual username instead of just the ID number
    assigned_to_name = serializers.ReadOnlyField(source='assigned_to.username')

    class Meta:
        model = Asset
        fields = '__all__'

class MaintenanceSerializer(serializers.ModelSerializer):
    # Grabs related details for the table
    asset_name = serializers.ReadOnlyField(source='asset.assets_name')
    asset_string_id = serializers.ReadOnlyField(source='asset.assets_id')
    technician_name = serializers.ReadOnlyField(source='technician.username')
    asset_type = serializers.CharField(source='asset.assets_type', read_only=True)

    class Meta:
        model = Maintenance
        fields = ['id', 'asset_string_id', 'asset_name', 'asset_type', 'maintenance_type', 'technician_name', 'date', 'last_modified', 'status']

class IncidentSerializer(serializers.ModelSerializer):
    # Grabs the Reporter username and related Asset location
    reported_by_name = serializers.ReadOnlyField(source='reported_by.username')
    asset_location = serializers.ReadOnlyField(source='asset.location')

    class Meta:
        model = Incident
        fields = '__all__'