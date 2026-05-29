from django.db import models
from simple_history.models import HistoricalRecords


class UploadBatch(models.Model):
    """Tracks each file upload event."""
    SOURCE_CHOICES = [
        ('sap', 'SAP'),
        ('utility', 'Utility'),
        ('travel', 'Travel'),
    ]
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    row_count = models.IntegerField(default=0)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.source} – {self.original_filename} ({self.uploaded_at:%Y-%m-%d})"


class EmissionRecord(models.Model):
    """
    Single unified table for all emission data regardless of source.

    Design decision: One table with source-typed fields rather than
    three separate tables. This lets analysts query across sources,
    apply uniform approval workflows, and push one schema to auditors.
    We store both raw_* (original messy values) and cleaned values so
    we can always trace back to the source document.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    SOURCE_CHOICES = [
        ('sap', 'SAP'),
        ('utility', 'Utility'),
        ('travel', 'Travel'),
    ]

    SCOPE_CHOICES = [
        ('scope1', 'Scope 1'),
        ('scope2', 'Scope 2'),
        ('scope3', 'Scope 3'),
    ]

    UNIT_CHOICES = [
        ('litres', 'Litres'),
        ('gallons', 'Gallons'),
        ('kwh', 'kWh'),
        ('km', 'Kilometres'),
        ('kg_co2e', 'kg CO₂e'),
    ]

    # ── Provenance ────────────────────────────────────────────────────────────
    batch = models.ForeignKey(UploadBatch, on_delete=models.CASCADE,
                              related_name='records')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    source_row_id = models.CharField(max_length=100, blank=True,
        help_text="Row identifier from the original file (e.g. SAP doc number)")

    # ── Raw (original, untouched) ─────────────────────────────────────────────
    raw_data = models.JSONField(
        help_text="The original row as parsed from the file before any cleaning")

    # ── Cleaned canonical fields ───────────────────────────────────────────────
    activity_date = models.DateField(null=True, blank=True,
        help_text="Normalised activity date (billing period start for utilities)")
    period_end = models.DateField(null=True, blank=True,
        help_text="End of billing / activity period")

    vendor_or_provider = models.CharField(max_length=255, blank=True,
        help_text="Supplier, utility company, airline, hotel, or taxi provider")

    description = models.TextField(blank=True,
        help_text="Human-readable description of the activity")

    # Quantity always stored in SI base unit (litres, kWh, km)
    quantity = models.FloatField(null=True, blank=True,
        help_text="Quantity in the normalised unit below")
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, blank=True)
    raw_quantity = models.FloatField(null=True, blank=True,
        help_text="Original quantity before unit conversion")
    raw_unit = models.CharField(max_length=50, blank=True,
        help_text="Original unit string from the source file")

    # Carbon
    co2e_kg = models.FloatField(null=True, blank=True,
        help_text="CO₂ equivalent in kg (calculated during parsing)")
    emission_factor_used = models.FloatField(null=True, blank=True,
        help_text="Emission factor applied (kg CO₂e per unit)")
    emission_factor_source = models.CharField(max_length=255, blank=True,
        help_text="Reference for the emission factor e.g. DEFRA 2023")

    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, blank=True)

    # Travel-specific
    origin_iata = models.CharField(max_length=4, blank=True)
    destination_iata = models.CharField(max_length=4, blank=True)
    distance_km = models.FloatField(null=True, blank=True)
    travel_mode = models.CharField(max_length=50, blank=True,
        help_text="flight, hotel, taxi, etc.")

    # Cost (optional but useful for auditors)
    cost_amount = models.FloatField(null=True, blank=True)
    cost_currency = models.CharField(max_length=10, blank=True)

    # ── Analyst review ────────────────────────────────────────────────────────
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default='pending')
    analyst_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # Audit log via django-simple-history
    history = HistoricalRecords()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-activity_date', '-created_at']
        indexes = [
            models.Index(fields=['source', 'status']),
            models.Index(fields=['activity_date']),
            models.Index(fields=['scope']),
        ]

    def __str__(self):
        return f"[{self.source.upper()}] {self.activity_date} – {self.description[:50]}"
