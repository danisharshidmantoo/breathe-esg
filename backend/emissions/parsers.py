"""
Data parsers for the three emission sources.

Each parser:
  1. Accepts a file-like object
  2. Cleans and normalises data
  3. Returns a list of dicts ready to bulk-create EmissionRecord objects

Design principle: keep raw_data untouched, transform to canonical fields.
"""

import io
import math
import re
from datetime import date, datetime
from typing import Any

import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# Emission factors (kg CO₂e per unit) – DEFRA 2023 as default
# In production these should live in the DB and be admin-configurable.
# ─────────────────────────────────────────────────────────────────────────────
EF = {
    # Fuel
    'diesel_litre': 2.68,
    'petrol_litre': 2.31,
    'natural_gas_kwh': 0.183,
    # Electricity (UK grid default; override per geography in production)
    'electricity_kwh': 0.233,
    # Travel
    'flight_km_economy': 0.255,   # per passenger-km
    'flight_km_business': 0.428,
    'hotel_night': 31.0,          # kg CO₂e per room-night (DEFRA)
    'taxi_km': 0.21,
}

EF_SOURCE = "DEFRA 2023 GHG Conversion Factors"

GALLONS_TO_LITRES = 3.78541

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_float(val):
    try:
        return float(str(val).replace(',', '').strip())
    except (ValueError, TypeError):
        return None


def _clean_raw(row_dict: dict) -> dict:
    """Replace NaN/inf with None so the dict is JSON-serialisable."""
    import math
    cleaned = {}
    for k, v in row_dict.items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            cleaned[k] = None
        else:
            cleaned[k] = v
    return cleaned


def _parse_date(val) -> date | None:
    if pd.isna(val) if hasattr(pd, 'isna') else val is None:
        return None
    if isinstance(val, (date, datetime)):
        return val.date() if isinstance(val, datetime) else val
    for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(str(val).strip(), fmt).date()
        except ValueError:
            pass
    return None


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance between two lat/lon points."""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# Minimal airport coordinate lookup (expand with full IATA DB in production)
AIRPORT_COORDS = {
    'LHR': (51.477, -0.461),
    'JFK': (40.641, -73.778),
    'DEL': (28.557, 77.088),
    'BOM': (19.088, 72.868),
    'BLR': (13.198, 77.706),
    'DXB': (25.252, 55.364),
    'CDG': (49.009, 2.548),
    'SIN': (1.350, 103.994),
    'HKG': (22.309, 113.915),
    'SYD': (-33.946, 151.177),
    'LAX': (33.942, -118.408),
    'ORD': (41.978, -87.904),
    'FRA': (50.033, 8.571),
    'AMS': (52.308, 4.764),
    'MUC': (48.354, 11.786),
    'MAA': (12.990, 80.169),
    'HYD': (17.231, 78.430),
}


def _distance_km(origin: str, dest: str) -> float | None:
    o = AIRPORT_COORDS.get(origin.upper())
    d = AIRPORT_COORDS.get(dest.upper())
    if o and d:
        return round(_haversine_km(*o, *d), 1)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# German → English column name mapping (SAP exports)
# ─────────────────────────────────────────────────────────────────────────────
SAP_COL_MAP = {
    'buchungsdatum': 'posting_date',
    'belegdatum': 'document_date',
    'lieferant': 'vendor',
    'lieferantenname': 'vendor_name',
    'material': 'material',
    'materialbezeichnung': 'material_description',
    'menge': 'quantity',
    'mengeneinheit': 'unit',
    'betrag': 'amount',
    'währung': 'currency',
    'belegnummer': 'document_number',
    'kostenstelle': 'cost_center',
    'werk': 'plant',
    # English variants already found in some exports
    'posting date': 'posting_date',
    'vendor': 'vendor',
    'quantity': 'quantity',
    'amount': 'amount',
    'currency': 'currency',
    'material description': 'material_description',
    'document number': 'document_number',
}


def _normalise_sap_cols(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower() for c in df.columns]
    df.rename(columns=SAP_COL_MAP, inplace=True)
    return df


FUEL_KEYWORDS = ['diesel', 'petrol', 'benzin', 'kraftstoff', 'fuel', 'gas', 'natural gas']


def _detect_fuel_type(desc: str) -> str:
    d = str(desc).lower()
    if 'diesel' in d:
        return 'diesel'
    if 'petrol' in d or 'benzin' in d:
        return 'petrol'
    if 'natural gas' in d or 'erdgas' in d:
        return 'natural_gas'
    return 'diesel'  # conservative default


# ─────────────────────────────────────────────────────────────────────────────
# SAP Parser
# ─────────────────────────────────────────────────────────────────────────────

def parse_sap(file_obj) -> list[dict[str, Any]]:
    """
    Parse SAP fuel/procurement CSV export.
    Handles: German column names, mixed gallons/litres units.
    Scope 1 (direct fuel combustion).
    """
    df = pd.read_csv(file_obj, encoding='utf-8-sig', sep=None, engine='python')
    df = _normalise_sap_cols(df)

    records = []
    for _, row in df.iterrows():
        raw = _clean_raw(row.to_dict())

        raw_qty = _safe_float(row.get('quantity'))
        raw_unit_str = str(row.get('unit', '')).strip().lower()
        desc = str(row.get('material_description', row.get('material', ''))).strip()

        # Unit normalisation: gallons → litres
        if raw_unit_str in ('gal', 'gallon', 'gallons', 'usg'):
            qty_litres = (raw_qty or 0) * GALLONS_TO_LITRES
            norm_unit = 'litres'
        elif raw_unit_str in ('l', 'ltr', 'litre', 'litres', 'liter', 'liters', 'l.'):
            qty_litres = raw_qty
            norm_unit = 'litres'
        elif raw_unit_str in ('kwh', 'kw/h'):
            qty_litres = raw_qty
            norm_unit = 'kwh'
        else:
            qty_litres = raw_qty
            norm_unit = raw_unit_str or 'litres'

        fuel_type = _detect_fuel_type(desc)
        if norm_unit == 'kwh':
            ef = EF['natural_gas_kwh']
        else:
            ef = EF.get(f'{fuel_type}_litre', EF['diesel_litre'])

        co2e = round((qty_litres or 0) * ef, 4) if qty_litres else None

        records.append({
            'source': 'sap',
            'source_row_id': str(row.get('document_number', '')),
            'raw_data': raw,
            'activity_date': _parse_date(row.get('posting_date') or row.get('document_date')),
            'vendor_or_provider': str(row.get('vendor_name', row.get('vendor', ''))).strip(),
            'description': desc,
            'quantity': qty_litres,
            'unit': norm_unit,
            'raw_quantity': raw_qty,
            'raw_unit': raw_unit_str,
            'co2e_kg': co2e,
            'emission_factor_used': ef,
            'emission_factor_source': EF_SOURCE,
            'scope': 'scope1',
            'cost_amount': _safe_float(row.get('amount')),
            'cost_currency': str(row.get('currency', '')).strip(),
        })

    return records


# ─────────────────────────────────────────────────────────────────────────────
# Utility Parser (CSV path; PDF handled separately via pdfplumber)
# ─────────────────────────────────────────────────────────────────────────────

UTILITY_COL_MAP = {
    'bill date': 'bill_date',
    'billing date': 'bill_date',
    'service from': 'period_start',
    'from': 'period_start',
    'service to': 'period_end',
    'to': 'period_end',
    'supplier': 'supplier',
    'provider': 'supplier',
    'utility company': 'supplier',
    'consumption': 'kwh',
    'units': 'kwh',
    'kwh': 'kwh',
    'energy (kwh)': 'kwh',
    'amount': 'amount',
    'total': 'amount',
    'currency': 'currency',
    'account number': 'account_number',
    'meter number': 'account_number',
    'site': 'site',
    'location': 'site',
}


def parse_utility_csv(file_obj) -> list[dict[str, Any]]:
    """
    Parse electricity utility bill CSV.
    Handles: billing periods that don't align to calendar months.
    Scope 2 (purchased electricity).
    """
    df = pd.read_csv(file_obj, encoding='utf-8-sig', sep=None, engine='python')
    df.columns = [c.strip().lower() for c in df.columns]
    df.rename(columns=UTILITY_COL_MAP, inplace=True)

    records = []
    for _, row in df.iterrows():
        raw = _clean_raw(row.to_dict())

        kwh = _safe_float(row.get('kwh'))
        period_start = _parse_date(row.get('period_start') or row.get('bill_date'))
        period_end = _parse_date(row.get('period_end'))
        co2e = round(kwh * EF['electricity_kwh'], 4) if kwh else None

        records.append({
            'source': 'utility',
            'source_row_id': str(row.get('account_number', '')),
            'raw_data': raw,
            'activity_date': period_start,
            'period_end': period_end,
            'vendor_or_provider': str(row.get('supplier', '')).strip(),
            'description': f"Electricity – {row.get('site', 'Unknown site')}",
            'quantity': kwh,
            'unit': 'kwh',
            'raw_quantity': kwh,
            'raw_unit': 'kwh',
            'co2e_kg': co2e,
            'emission_factor_used': EF['electricity_kwh'],
            'emission_factor_source': EF_SOURCE,
            'scope': 'scope2',
            'cost_amount': _safe_float(row.get('amount')),
            'cost_currency': str(row.get('currency', 'GBP')).strip(),
        })

    return records


def parse_utility_pdf(file_obj) -> list[dict[str, Any]]:
    """
    Extract electricity data from utility bill PDFs using pdfplumber.
    Looks for kWh values and billing period dates using regex patterns.
    """
    import pdfplumber

    text = ''
    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            text += (page.extract_text() or '') + '\n'

    # Regex extractions (best-effort; expand patterns per provider)
    kwh_match = re.search(r'(\d[\d,]*\.?\d*)\s*kWh', text, re.IGNORECASE)
    kwh = _safe_float(kwh_match.group(1)) if kwh_match else None

    date_matches = re.findall(r'\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\b', text)
    dates = [_parse_date(d) for d in date_matches if _parse_date(d)]
    dates = sorted([d for d in dates if d], )

    period_start = dates[0] if len(dates) >= 1 else None
    period_end = dates[1] if len(dates) >= 2 else None

    amount_match = re.search(r'(?:total|amount due)[^\d]*(\d[\d,]*\.?\d*)', text, re.IGNORECASE)
    amount = _safe_float(amount_match.group(1)) if amount_match else None

    supplier_match = re.search(r'(?:from|supplier|provider)[:\s]+([A-Za-z &]+)', text, re.IGNORECASE)
    supplier = supplier_match.group(1).strip() if supplier_match else 'Unknown Utility'

    co2e = round(kwh * EF['electricity_kwh'], 4) if kwh else None

    return [{
        'source': 'utility',
        'source_row_id': '',
        'raw_data': {'pdf_text_excerpt': text[:500]},
        'activity_date': period_start,
        'period_end': period_end,
        'vendor_or_provider': supplier,
        'description': 'Electricity – extracted from PDF bill',
        'quantity': kwh,
        'unit': 'kwh',
        'raw_quantity': kwh,
        'raw_unit': 'kWh',
        'co2e_kg': co2e,
        'emission_factor_used': EF['electricity_kwh'],
        'emission_factor_source': EF_SOURCE,
        'scope': 'scope2',
        'cost_amount': amount,
        'cost_currency': 'GBP',
    }]


# ─────────────────────────────────────────────────────────────────────────────
# Travel Parser
# ─────────────────────────────────────────────────────────────────────────────

TRAVEL_COL_MAP = {
    'travel date': 'travel_date',
    'date': 'travel_date',
    'departure': 'origin',
    'origin': 'origin',
    'from': 'origin',
    'arrival': 'destination',
    'destination': 'destination',
    'to': 'destination',
    'type': 'travel_type',
    'mode': 'travel_type',
    'travel type': 'travel_type',
    'class': 'travel_class',
    'cabin class': 'travel_class',
    'hotel name': 'hotel',
    'hotel': 'hotel',
    'nights': 'nights',
    'employee': 'employee',
    'traveller': 'employee',
    'cost': 'cost',
    'amount': 'cost',
    'currency': 'currency',
}


def parse_travel(file_obj) -> list[dict[str, Any]]:
    """
    Parse travel expense CSV (flights, hotels, taxis).
    Handles: IATA airport codes → distance calculation via haversine.
    Scope 3 (business travel).
    """
    df = pd.read_csv(file_obj, encoding='utf-8-sig', sep=None, engine='python')
    df.columns = [c.strip().lower() for c in df.columns]
    df.rename(columns=TRAVEL_COL_MAP, inplace=True)

    records = []
    for _, row in df.iterrows():
        raw = _clean_raw(row.to_dict())

        mode = str(row.get('travel_type', 'flight')).lower().strip()
        travel_date = _parse_date(row.get('travel_date'))

        if 'flight' in mode or 'air' in mode:
            origin = str(row.get('origin', '')).upper().strip()[:4]
            dest = str(row.get('destination', '')).upper().strip()[:4]
            dist_km = _distance_km(origin, dest)
            cab = str(row.get('travel_class', 'economy')).lower()
            ef = EF['flight_km_business'] if 'bus' in cab or 'first' in cab else EF['flight_km_economy']
            co2e = round(dist_km * ef, 4) if dist_km else None
            desc = f"Flight {origin}→{dest}"
            qty = dist_km
            unit = 'km'

            records.append({
                'source': 'travel',
                'source_row_id': '',
                'raw_data': raw,
                'activity_date': travel_date,
                'vendor_or_provider': str(row.get('employee', '')).strip(),
                'description': desc,
                'quantity': qty,
                'unit': unit,
                'raw_quantity': None,
                'raw_unit': 'IATA codes',
                'co2e_kg': co2e,
                'emission_factor_used': ef,
                'emission_factor_source': EF_SOURCE,
                'scope': 'scope3',
                'origin_iata': origin,
                'destination_iata': dest,
                'distance_km': dist_km,
                'travel_mode': 'flight',
                'cost_amount': _safe_float(row.get('cost')),
                'cost_currency': str(row.get('currency', '')).strip(),
            })

        elif 'hotel' in mode or 'accommodation' in mode:
            nights = _safe_float(row.get('nights', 1)) or 1
            co2e = round(nights * EF['hotel_night'], 4)
            hotel = str(row.get('hotel', row.get('destination', ''))).strip()

            records.append({
                'source': 'travel',
                'source_row_id': '',
                'raw_data': raw,
                'activity_date': travel_date,
                'vendor_or_provider': hotel,
                'description': f"Hotel: {hotel} ({int(nights)} nights)",
                'quantity': nights,
                'unit': 'nights',
                'raw_quantity': nights,
                'raw_unit': 'nights',
                'co2e_kg': co2e,
                'emission_factor_used': EF['hotel_night'],
                'emission_factor_source': EF_SOURCE,
                'scope': 'scope3',
                'travel_mode': 'hotel',
                'cost_amount': _safe_float(row.get('cost')),
                'cost_currency': str(row.get('currency', '')).strip(),
            })

        else:  # taxi / ground transport
            dist_km = _safe_float(row.get('distance_km') or row.get('distance') or row.get('km'))
            co2e = round(dist_km * EF['taxi_km'], 4) if dist_km else None

            records.append({
                'source': 'travel',
                'source_row_id': '',
                'raw_data': raw,
                'activity_date': travel_date,
                'vendor_or_provider': str(row.get('employee', '')).strip(),
                'description': f"Ground transport – {mode}",
                'quantity': dist_km,
                'unit': 'km',
                'raw_quantity': dist_km,
                'raw_unit': 'km',
                'co2e_kg': co2e,
                'emission_factor_used': EF['taxi_km'],
                'emission_factor_source': EF_SOURCE,
                'scope': 'scope3',
                'distance_km': dist_km,
                'travel_mode': mode,
                'cost_amount': _safe_float(row.get('cost')),
                'cost_currency': str(row.get('currency', '')).strip(),
            })

    return records