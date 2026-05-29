from rest_framework import serializers
from .models import EmissionRecord, UploadBatch


class UploadBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadBatch
        fields = '__all__'


class EmissionRecordSerializer(serializers.ModelSerializer):
    batch_source = serializers.CharField(source='batch.source', read_only=True)

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'batch', 'batch_source', 'source', 'source_row_id',
            'raw_data',
            'activity_date', 'period_end',
            'vendor_or_provider', 'description',
            'quantity', 'unit', 'raw_quantity', 'raw_unit',
            'co2e_kg', 'emission_factor_used', 'emission_factor_source',
            'scope',
            'origin_iata', 'destination_iata', 'distance_km', 'travel_mode',
            'cost_amount', 'cost_currency',
            'status', 'analyst_note', 'reviewed_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'batch_source']


class EmissionRecordUpdateSerializer(serializers.ModelSerializer):
    """Restricted serializer for analyst review actions."""
    class Meta:
        model = EmissionRecord
        fields = ['status', 'analyst_note', 'co2e_kg', 'reviewed_at']
