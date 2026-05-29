import io
from datetime import datetime

from django.db import transaction
from django.db.models import Sum, Count, Q
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import EmissionRecord, UploadBatch
from .parsers import parse_sap, parse_utility_csv, parse_utility_pdf, parse_travel
from .serializers import (
    EmissionRecordSerializer,
    EmissionRecordUpdateSerializer,
    UploadBatchSerializer,
)


class UploadView(APIView):
    """
    POST /api/upload/
    Accepts a file + source type, runs the right parser,
    bulk-creates records in one transaction.
    """

    def post(self, request):
        source = request.data.get('source')
        file_obj = request.FILES.get('file')

        if not source or not file_obj:
            return Response(
                {'error': 'Both source and file are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if source not in ('sap', 'utility', 'travel'):
            return Response(
                {'error': f'Invalid source "{source}". Must be sap, utility, or travel.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        filename = file_obj.name.lower()

        try:
            file_bytes = file_obj.read()

            if source == 'sap':
                records_data = parse_sap(io.BytesIO(file_bytes))

            elif source == 'utility':
                if filename.endswith('.pdf'):
                    records_data = parse_utility_pdf(io.BytesIO(file_bytes))
                else:
                    records_data = parse_utility_csv(io.BytesIO(file_bytes))

            elif source == 'travel':
                records_data = parse_travel(io.BytesIO(file_bytes))

        except Exception as exc:
            return Response(
                {'error': f'Parse error: {str(exc)}'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

        with transaction.atomic():
            batch = UploadBatch.objects.create(
                source=source,
                original_filename=file_obj.name,
                row_count=len(records_data),
            )

            records = []
            for rd in records_data:
                # Strip batch key if accidentally included
                rd.pop('batch', None)
                records.append(EmissionRecord(batch=batch, **rd))

            EmissionRecord.objects.bulk_create(records)

        return Response(
            {
                'batch_id': batch.id,
                'source': source,
                'rows_created': len(records_data),
                'message': f'{len(records_data)} records imported successfully.',
            },
            status=status.HTTP_201_CREATED
        )


class EmissionRecordViewSet(viewsets.ModelViewSet):
    """
    GET  /api/records/          – list with filters
    GET  /api/records/{id}/     – single record
    PATCH /api/records/{id}/    – analyst update (status, note)
    POST /api/records/{id}/approve/
    POST /api/records/{id}/reject/
    """
    queryset = EmissionRecord.objects.select_related('batch').all()
    serializer_class = EmissionRecordSerializer

    def get_serializer_class(self):
        if self.action in ('partial_update', 'update'):
            return EmissionRecordUpdateSerializer
        return EmissionRecordSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        source = params.get('source')
        status_filter = params.get('status')
        scope = params.get('scope')
        date_from = params.get('date_from')
        date_to = params.get('date_to')
        search = params.get('search')

        if source:
            qs = qs.filter(source=source)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if scope:
            qs = qs.filter(scope=scope)
        if date_from:
            qs = qs.filter(activity_date__gte=date_from)
        if date_to:
            qs = qs.filter(activity_date__lte=date_to)
        if search:
            qs = qs.filter(
                Q(description__icontains=search) |
                Q(vendor_or_provider__icontains=search)
            )
        return qs

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        record = self.get_object()
        record.status = 'approved'
        record.reviewed_at = datetime.utcnow()
        record.analyst_note = request.data.get('note', record.analyst_note)
        record.save()
        return Response(EmissionRecordSerializer(record).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        record = self.get_object()
        record.status = 'rejected'
        record.reviewed_at = datetime.utcnow()
        record.analyst_note = request.data.get('note', record.analyst_note)
        record.save()
        return Response(EmissionRecordSerializer(record).data)

    @action(detail=False, methods=['post'])
    def bulk_approve(self, request):
        ids = request.data.get('ids', [])
        updated = EmissionRecord.objects.filter(id__in=ids, status='pending').update(
            status='approved', reviewed_at=datetime.utcnow()
        )
        return Response({'updated': updated})


@api_view(['GET'])
def stats_view(request):
    """GET /api/stats/ – summary numbers for the dashboard header."""
    qs = EmissionRecord.objects.all()
    return Response({
        'total_records': qs.count(),
        'pending': qs.filter(status='pending').count(),
        'approved': qs.filter(status='approved').count(),
        'rejected': qs.filter(status='rejected').count(),
        'total_co2e_kg': qs.filter(status='approved').aggregate(
            t=Sum('co2e_kg'))['t'] or 0,
        'by_scope': {
            s: qs.filter(scope=s).aggregate(t=Sum('co2e_kg'))['t'] or 0
            for s in ['scope1', 'scope2', 'scope3']
        },
        'by_source': {
            src: qs.filter(source=src).count()
            for src in ['sap', 'utility', 'travel']
        },
    })
