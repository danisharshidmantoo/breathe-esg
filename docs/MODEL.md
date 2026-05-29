# Data Model

## Core design: One unified table

```
UploadBatch (1) ──────────── (*) EmissionRecord
```

### Why one table?

Analysts query across sources, auditors receive one schema, and the approval workflow is identical regardless of source. Future sources slot in without schema changes.

## EmissionRecord — key fields

| Field | Type | Why it exists |
|-------|------|---------------|
| `source` | CharField | Which parser created this row: sap, utility, travel |
| `raw_data` | JSONField | Original row before any cleaning — immutable audit trail |
| `activity_date` | DateField | Normalised activity start date |
| `period_end` | DateField | Billing period end for utilities (NULL for SAP/travel) |
| `quantity` | FloatField | Always in SI base unit (litres, kWh, km, nights) |
| `raw_quantity` / `raw_unit` | Float/Char | Original value/unit before conversion (e.g. 50 gallons) |
| `co2e_kg` | FloatField | Calculated carbon; analyst can override |
| `emission_factor_used` | FloatField | The factor applied — stored for traceability |
| `emission_factor_source` | CharField | e.g. "DEFRA 2023 GHG Conversion Factors" |
| `scope` | CharField | scope1 / scope2 / scope3 per GHG Protocol |
| `origin_iata` / `destination_iata` | CharField | Raw airport codes from travel data |
| `distance_km` | FloatField | Computed via haversine; NULL if airports unknown |
| `status` | CharField | pending → approved or rejected |
| `history` | (auto) | Full change history via django-simple-history |

## Indexes

```python
Index(fields=['source', 'status'])   # Dashboard filter queries
Index(fields=['activity_date'])       # Date range queries
Index(fields=['scope'])               # Scope breakdown queries
```
