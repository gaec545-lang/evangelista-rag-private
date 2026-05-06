"""
Herramienta: Generador de Queries SQL de auditoría para ERPs mexicanos.
Soporta SAP B1, CONTPAQi, Aspel y Microsip.
"""
from __future__ import annotations

# Plantillas de queries por ERP y objetivo de auditoría
_TEMPLATES: dict[str, dict[str, str]] = {
    "sap_b1": {
        "inventario_sin_movimiento": """
-- SAP B1: Artículos sin movimiento en los últimos 180 días
SELECT
    T0.ItemCode,
    T0.ItemName,
    T0.OnHand          AS stock_actual,
    T0.OnOrder         AS en_pedido,
    T0.AvgPrice        AS precio_promedio,
    T0.OnHand * T0.AvgPrice AS valor_inventario,
    MAX(T1.DocDate)    AS ultima_transaccion
FROM OITM T0
LEFT JOIN OINM T1 ON T0.ItemCode = T1.ItemCode
WHERE T0.OnHand > 0
  AND T0.InvntItem = 'Y'
GROUP BY T0.ItemCode, T0.ItemName, T0.OnHand, T0.OnOrder, T0.AvgPrice
HAVING MAX(T1.DocDate) < DATEADD(DAY, -180, GETDATE())
    OR MAX(T1.DocDate) IS NULL
ORDER BY valor_inventario DESC;
""",
        "cartera_vencida": """
-- SAP B1: Facturas vencidas por cliente
SELECT
    T0.CardCode,
    T0.CardName,
    T0.DocNum,
    T0.DocDate         AS fecha_factura,
    T0.DocDueDate      AS fecha_vencimiento,
    DATEDIFF(DAY, T0.DocDueDate, GETDATE()) AS dias_vencido,
    T0.DocTotal        AS total_factura,
    T0.PaidToDate      AS pagado,
    T0.DocTotal - T0.PaidToDate AS saldo_pendiente
FROM OINV T0
WHERE T0.DocStatus = 'O'
  AND T0.DocDueDate < GETDATE()
ORDER BY dias_vencido DESC, saldo_pendiente DESC;
""",
        "diferencias_inventario": """
-- SAP B1: Diferencias entre inventario físico y sistema
SELECT
    T0.ItemCode,
    T0.ItemName,
    T0.OnHand          AS sistema,
    T1.Counted         AS conteo_fisico,
    T1.Counted - T0.OnHand AS diferencia,
    ABS(T1.Counted - T0.OnHand) * T0.AvgPrice AS impacto_mxn
FROM OITM T0
JOIN OINC T1 ON T0.ItemCode = T1.ItemCode
WHERE ABS(T1.Counted - T0.OnHand) > 0
ORDER BY impacto_mxn DESC;
""",
    },
    "contpaqi": {
        "inventario_sin_movimiento": """
-- CONTPAQi: Artículos sin movimiento (últimos 180 días)
SELECT
    P.CCODIGOPRODUCTO    AS clave,
    P.CNOMBREPRODUCTO    AS descripcion,
    E.CUNIDADES          AS existencia,
    E.CCOSTO             AS costo_promedio,
    E.CUNIDADES * E.CCOSTO AS valor_inventario,
    MAX(M.CFECHA)        AS ultimo_movimiento
FROM admProductos P
JOIN admExistencias E ON P.CIDPRODUCTO = E.CIDPRODUCTO
LEFT JOIN admMovimientos M ON P.CIDPRODUCTO = M.CIDPRODUCTO
WHERE E.CUNIDADES > 0
GROUP BY P.CCODIGOPRODUCTO, P.CNOMBREPRODUCTO, E.CUNIDADES, E.CCOSTO
HAVING MAX(M.CFECHA) < DATEADD(DAY, -180, GETDATE())
    OR MAX(M.CFECHA) IS NULL
ORDER BY valor_inventario DESC;
""",
        "cartera_vencida": """
-- CONTPAQi: Cuentas por cobrar vencidas
SELECT
    C.CRAZONSOCIAL       AS cliente,
    C.CRFC               AS rfc,
    D.CFOLIO             AS folio,
    D.CFECHA             AS fecha,
    D.CFECHAVENCIMIENTO  AS vencimiento,
    DATEDIFF(DAY, D.CFECHAVENCIMIENTO, GETDATE()) AS dias_vencido,
    D.CTOTAL             AS total,
    D.CSALDOPENDIENTE    AS saldo
FROM admClientes C
JOIN admDocumentos D ON C.CIDCLIENTE = D.CIDCLIENTE
WHERE D.CIDDOCUMENTODE = 1   -- Facturas
  AND D.CESTADO = 1           -- Pendientes
  AND D.CFECHAVENCIMIENTO < GETDATE()
ORDER BY dias_vencido DESC;
""",
    },
    "aspel": {
        "inventario_sin_movimiento": """
-- Aspel SAE: Artículos sin movimiento
SELECT
    A.CLAVE,
    A.DESCRIPCION,
    A.EXIST           AS existencia,
    A.COSTOPROM       AS costo_promedio,
    A.EXIST * A.COSTOPROM AS valor_inventario,
    MAX(M.FECHA)      AS ultimo_movimiento
FROM PRODU A
LEFT JOIN MOVIC M ON A.CLAVE = M.CLAVE
WHERE A.EXIST > 0
GROUP BY A.CLAVE, A.DESCRIPCION, A.EXIST, A.COSTOPROM
HAVING MAX(M.FECHA) < DATEADD(DAY, -180, GETDATE())
    OR MAX(M.FECHA) IS NULL
ORDER BY valor_inventario DESC;
""",
    },
}

_ERP_ALIASES = {
    "sap": "sap_b1",
    "sap b1": "sap_b1",
    "sap business one": "sap_b1",
    "contpaqi": "contpaqi",
    "adminpaq": "contpaqi",
    "aspel": "aspel",
    "aspel sae": "aspel",
}

_GOAL_ALIASES = {
    "inventario": "inventario_sin_movimiento",
    "sin movimiento": "inventario_sin_movimiento",
    "merma": "inventario_sin_movimiento",
    "cartera": "cartera_vencida",
    "cuentas por cobrar": "cartera_vencida",
    "cobranza": "cartera_vencida",
    "diferencias": "diferencias_inventario",
    "faltantes": "diferencias_inventario",
}


class SqlAuditGenerator:
    """Generador de queries SQL de auditoría para ERPs mexicanos."""

    def generate(self, erp_type: str, audit_goal: str) -> str:
        """Retorna la query SQL para el ERP y objetivo dados."""
        erp_key = _ERP_ALIASES.get(erp_type.lower(), erp_type.lower())
        goal_key = _GOAL_ALIASES.get(audit_goal.lower(), audit_goal.lower())

        erp_templates = _TEMPLATES.get(erp_key)
        if not erp_templates:
            available = ", ".join(_TEMPLATES.keys())
            return f"-- ERP '{erp_type}' no soportado. Disponibles: {available}"

        query = erp_templates.get(goal_key)
        if not query:
            available = ", ".join(erp_templates.keys())
            return f"-- Objetivo '{audit_goal}' no disponible para {erp_type}. Disponibles: {available}"

        return query.strip()

    def generate_from_text(self, text: str) -> str:
        """Infiere ERP y objetivo desde texto libre y genera la query."""
        text_lower = text.lower()

        # Detectar ERP
        erp = "sap_b1"  # Default más común en PyMEs
        for alias, key in _ERP_ALIASES.items():
            if alias in text_lower:
                erp = key
                break

        # Detectar objetivo
        goal = "inventario_sin_movimiento"  # Default
        for alias, key in _GOAL_ALIASES.items():
            if alias in text_lower:
                goal = key
                break

        query = _TEMPLATES.get(erp, {}).get(goal, "")
        if not query:
            return f"-- No se encontró template para {erp}/{goal}"

        return f"-- Auto-generado para {erp} | objetivo: {goal}\n{query.strip()}"
