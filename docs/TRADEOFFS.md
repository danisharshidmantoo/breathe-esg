# Tradeoffs & What We Did NOT Build

## Deliberately not built

**Authentication:** Adding Django auth + JWT would take 4+ hours. simple-history already supports stamping changes with user IDs once auth is wired up.

**Per-provider PDF extractors:** Our PDF parser uses generic regex. Real utility PDFs (British Gas vs EDF) have different layouts. Production needs one extractor class per provider. The scaffold is built; the patterns are the variable.

**Scope 3 disaggregation:** GHG Protocol has 15 Scope 3 categories. We tag everything as scope3. Production needs a scope3_category field.

**Currency normalisation:** Cost fields store raw amounts without FX conversion. Informational only; CO2e is the primary metric.

**Duplicate detection:** Uploading the same file twice creates duplicates. Production needs a unique constraint on source + document_number + activity_date.

**Frontend pagination:** API has PageNumberPagination(50). Frontend fetches one page. Not observable with sample data.

## Key tradeoffs

| Choice | Benefit | Cost |
|--------|---------|------|
| One unified table | Simple queries, single approval flow | Nullable fields for source-specific data |
| Haversine distance | No API dependency | NULL for unknown IATA pairs |
| raw_data as JSON | Full auditability | JSONField queries slower than normalised columns |
| DEFRA factors hardcoded | No admin overhead | Must redeploy to update factors |
