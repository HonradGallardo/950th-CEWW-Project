from rest_framework import serializers
from .models import Asset, Maintenance, Incident

class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = '__all__'

class MaintenanceSerializer(serializers.ModelSerializer):
    asset_name = serializers.ReadOnlyField(source='asset.assets_name')
    class Meta:
        model = Maintenance
        fields = '__all__'

class IncidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Incident
        fields = '__all__'