"""Code-based data profiling for auto-detecting Foundation scoping parameters.

No LLM involved — pure statistical analysis of CSV/Excel files or database connections.
"""
import csv
import io
from pathlib import Path
from typing import Any

import pandas as pd


def profile_csv(file_path: str | Path) -> dict[str, Any]:
    """Profile a CSV/Excel file and detect scoping parameters.

    Returns dict with detected params + confidence scores.
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix in (".csv", ".tsv"):
        sep = "\t" if suffix == ".tsv" else ","
        df = pd.read_csv(file_path, sep=sep, nrows=100_000)
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(file_path, nrows=100_000)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")

    return profile_dataframe(df, file_path.name)


def profile_dataframe(df: pd.DataFrame, filename: str = "uploaded") -> dict[str, Any]:
    """Profile an in-memory pandas DataFrame.

    Returns:
        {
            "registros_estimados": int,
            "fuentes_datos": int,
            "nodo_critico": str | None,
            "sucursales": int,
            "erp_type": str | None,
            "confidence_scores": dict,
            "column_profile": list[dict],
        }
    """
    row_count = len(df)
    column_count = len(df.columns)
    col_names_lower = [c.lower() for c in df.columns]

    # ── Registro count (always reliable) ──
    registros = int(row_count)

    # ── Detect ERP type ──
    erp_type = _detect_erp_type(col_names_lower, df)

    # ── Detect critical node ──
    nodo_critico = _detect_nodo_critico(col_names_lower, df)

    # ── Detect locations/sucursales ──
    sucursales = _count_sucursales(col_names_lower, df)

    # ── Estimate data sources ──
    fuentes = _estimate_fuentes(column_count, col_names_lower, erp_type)

    # ── Column profile for UI display ──
    column_profile = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        null_pct = float(df[col].isna().mean() * 100)
        unique_count = int(df[col].nunique())
        column_profile.append(
            {
                "name": col,
                "dtype": dtype,
                "null_pct": round(null_pct, 1),
                "unique_count": unique_count,
            }
        )

    # ── Confidence scores ──
    confidence = {
        "registros": 0.99,  # COUNT is always exact
        "erp_type": 0.8 if erp_type else 0.0,
        "nodo_critico": 0.7 if nodo_critico else 0.0,
        "sucursales": min(0.95, 0.5 + (sucursales > 0) * 0.45),
        "fuentes": 0.6,  # heuristic-based
    }

    return {
        "registros_estimados": registros,
        "fuentes_datos": fuentes,
        "nodo_critico": nodo_critico,
        "sucursales": sucursales,
        "erp_type": erp_type,
        "confidence_scores": confidence,
        "column_profile": column_profile,
        "row_count": row_count,
        "column_count": column_count,
    }


def _detect_erp_type(col_names: list[str], df: pd.DataFrame) -> str | None:
    """Detect ERP system from column naming patterns."""
    cols_text = " ".join(col_names)

    sap_indicators = [
        "bukrs", "mandt", "matnr", "kunnr", "lifnr", "belnr",
        "bktxt", "sgtxt", "hkont", "kostl", "aufnr",
        "sap_", "sap", "bseg", "bkpf", "marc", "lfa1",
    ]
    oracle_indicators = [
        "org_id", "ledger_id", "code_combination", "segment1",
        "inventory_org", "oracle_", "ebs_", "fusion_",
    ]
    dynamics_indicators = [
        "dataareaid", "partition_id", "recid", "createdby",
        "dynamics_", "ax_", "d365_", "fno_",
    ]
    netsuite_indicators = [
        "custentity", "custrecord", "internalid", "subsidiary_id",
        "netsuite", "ns_", "scriptid",
    ]

    scores = {"SAP": 0, "Oracle EBS": 0, "Dynamics 365/AX": 0, "NetSuite": 0}
    for ind in sap_indicators:
        scores["SAP"] += cols_text.count(ind)
    for ind in oracle_indicators:
        scores["Oracle EBS"] += cols_text.count(ind)
    for ind in dynamics_indicators:
        scores["Dynamics 365/AX"] += cols_text.count(ind)
    for ind in netsuite_indicators:
        scores["NetSuite"] += cols_text.count(ind)

    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None


def _detect_nodo_critico(col_names: list[str], df: pd.DataFrame) -> str | None:
    """Identify the critical data node (primary ERP system)."""
    # Already detected ERP type
    erp = _detect_erp_type(col_names, df)

    if erp:
        return erp

    # Check for known accounting/ERP table names
    table_indicators = []
    for col in col_names:
        if any(x in col for x in ["cuenta", "asiento", "poliza", "diario"]):
            table_indicators.append("contabilidad")
        if any(x in col for x in ["nomina", "empleado", "salario", "payroll"]):
            table_indicators.append("nomina")
        if any(x in col for x in ["inventario", "producto", "almacen", "stock"]):
            table_indicators.append("inventario")
        if any(x in col for x in ["cliente", "proveedor", "vendor", "customer"]):
            table_indicators.append("terceros")

    # Most common domain becomes the critical node
    if table_indicators:
        from collections import Counter
        return Counter(table_indicators).most_common(1)[0][0]

    return None


def _count_sucursales(col_names: list[str], df: pd.DataFrame) -> int:
    """Estimate number of branches/locations."""
    # Look for branch/location columns
    location_cols = []
    for col in df.columns:
        col_lower = col.lower()
        if any(
            x in col_lower
            for x in ["sucursal", "branch", "planta", "tienda", "ubicacion",
                      "location", "site", "centro", "delegacion", "ciudad"]
        ):
            location_cols.append(col)

    if not location_cols:
        return 1  # default assumption

    # Use the column with most unique values
    best_col = max(location_cols, key=lambda c: df[c].nunique())
    unique_count = int(df[best_col].nunique())
    # Fill NaN as separate "branch" would be wrong, exclude them
    unique_valid = int(df[best_col].dropna().nunique())
    return max(1, unique_valid)


def _estimate_fuentes(
    column_count: int, col_names: list[str], erp_type: str | None
) -> int:
    """Estimate number of data sources (tables/systems)."""
    # Heuristic: more ERP systems = more data sources
    base = 1
    if erp_type:
        base += 1
    # Detect domain diversity
    domains = set()
    for col in col_names:
        if any(x in col for x in ["cuenta", "asiento", "monto", "saldo", "importe", "debito", "credito"]):
            domains.add("contabilidad")
        if any(x in col for x in ["producto", "inventario", "stock", "item", "sku"]):
            domains.add("inventario")
        if any(x in col for x in ["nomina", "empleado", "salario", "departamento"]):
            domains.add("nomina")
        if any(x in col for x in ["cliente", "proveedor", "factura", "invoice"]):
            domains.add("cxc_cxp")
        if any(x in col for x in ["fecha", "date", "periodo", "anio", "mes"]):
            domains.add("temporal")
    return base + len(domains)
