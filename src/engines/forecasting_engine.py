"""
Forecasting Engine - Escudo 1 (Radar)
Evangelista & Co. | Sentinel Decision Intelligence V2

Proyecta series temporales a 1, 6 y 12 meses usando:
  - Darts (ExponentialSmoothing / NaiveDrift): ingresos y costos
  - Prophet (Facebook): estacionalidad y tendencias
  - ARCH/GARCH: volatilidad futura de variables macro (TIIE, USD/MXN)
"""

import logging
import warnings
import numpy as np
import pandas as pd
from datetime import datetime, date
from typing import Optional

# Suprimir warnings de librerías durante importación
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

logger = logging.getLogger(__name__)


# ── Helpers de importación segura ─────────────────────────────────────────────

def _import_darts():
    from darts import TimeSeries
    from darts.models import ExponentialSmoothing, NaiveDrift
    return TimeSeries, ExponentialSmoothing, NaiveDrift


def _import_prophet():
    from prophet import Prophet
    return Prophet


def _import_arch():
    from arch import arch_model
    return arch_model


# ── Generador de datos dummy para testing ─────────────────────────────────────

def _generate_dummy_series(n_months: int = 24, base: float = 500_000,
                            trend: float = 0.02, noise: float = 0.08,
                            seed: int = 42) -> pd.DataFrame:
    """Genera una serie temporal mensual con tendencia + ruido para testing."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(
        end=pd.Timestamp.now().normalize() - pd.offsets.MonthBegin(1),
        periods=n_months, freq="MS"
    )
    values = base * (1 + trend) ** np.arange(n_months)
    values *= 1 + rng.normal(0, noise, n_months)
    return pd.DataFrame({"fecha": dates, "valor": values.clip(min=0)})


# ── Motor principal ────────────────────────────────────────────────────────────

class ForecastingEngine:
    """
    Motor de proyección temporal usando Darts + Prophet + ARCH.

    Uso:
        engine = ForecastingEngine(supabase_creds, client_id)
        engine.load_data()
        ingresos  = engine.forecast_ingresos(horizonte_meses=12)
        costos    = engine.forecast_costos(horizonte_meses=12)
        volatilidad = engine.forecast_volatilidad('TIIE', horizonte_meses=6)
        resultados = engine.run_all(horizonte_meses=12)
    """

    def __init__(self, supabase_creds: Optional[dict] = None, client_id: Optional[str] = None):
        self.supabase_creds = supabase_creds
        self.client_id = client_id

        # DataFrames históricos (se pueblan en load_data)
        self._df_ingresos: Optional[pd.DataFrame] = None
        self._df_costos: Optional[pd.DataFrame] = None
        self._df_variables_exogenas: Optional[pd.DataFrame] = None

        logger.info(f"ForecastingEngine inicializado | client_id={client_id}")

    # ── Carga de datos ─────────────────────────────────────────────────────────

    def load_data(self, use_dummy: bool = False) -> None:
        """
        Carga datos históricos del cliente desde Supabase.

        Tablas esperadas (Supabase del cliente):
          - fact_proyectos  → columnas: fecha, monto_ingreso (o ingreso, monto_facturado)
          - fact_compras    → columnas: fecha, monto (o costo_total, importe)

        Tabla global Evangelista:
          - saas_variables_exogenas → variable, fecha, valor

        Si use_dummy=True o falla la conexión, usa datos sintéticos.
        """
        if use_dummy or not self.supabase_creds:
            logger.warning("ForecastingEngine: usando datos DUMMY (sin conexión a cliente)")
            self._load_dummy_data()
            return

        try:
            self._load_from_supabase()
        except Exception as e:
            logger.warning(f"Fallo carga Supabase, usando datos dummy: {e}")
            self._load_dummy_data()

    def _load_from_supabase(self) -> None:
        from supabase import create_client

        url = self.supabase_creds.get("url")
        key = self.supabase_creds.get("key")
        client = create_client(url, key)

        # --- Ingresos ---
        resp = client.table("fact_proyectos").select("*").execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            fecha_col = next((c for c in df.columns if "fecha" in c.lower()), None)
            ingreso_col = next(
                (c for c in df.columns if any(k in c.lower() for k in ["ingreso", "monto", "factur"])),
                None
            )
            if fecha_col and ingreso_col:
                self._df_ingresos = (
                    df[[fecha_col, ingreso_col]]
                    .rename(columns={fecha_col: "fecha", ingreso_col: "valor"})
                    .assign(fecha=lambda x: pd.to_datetime(x["fecha"]))
                    .dropna()
                    .sort_values("fecha")
                )

        # --- Costos ---
        resp = client.table("fact_compras").select("*").execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            fecha_col = next((c for c in df.columns if "fecha" in c.lower()), None)
            costo_col = next(
                (c for c in df.columns if any(k in c.lower() for k in ["monto", "costo", "importe", "total"])),
                None
            )
            if fecha_col and costo_col:
                self._df_costos = (
                    df[[fecha_col, costo_col]]
                    .rename(columns={fecha_col: "fecha", costo_col: "valor"})
                    .assign(fecha=lambda x: pd.to_datetime(x["fecha"]))
                    .dropna()
                    .sort_values("fecha")
                )

        if self._df_ingresos is None:
            raise ValueError("No se pudo extraer columna de ingresos de fact_proyectos")

    def _load_dummy_data(self) -> None:
        """Genera 24 meses de historia sintética para testing."""
        self._df_ingresos = _generate_dummy_series(24, base=650_000, trend=0.025, seed=1)
        self._df_costos   = _generate_dummy_series(24, base=420_000, trend=0.018, seed=2)
        # Exógenas: TIIE con ligera tendencia alcista
        dates = pd.date_range(end=pd.Timestamp.now(), periods=24, freq="MS")
        tiie = 10.5 + np.cumsum(np.random.default_rng(99).normal(0, 0.1, 24))
        self._df_variables_exogenas = pd.DataFrame({
            "variable": "TIIE",
            "fecha": dates,
            "valor": tiie.clip(min=5)
        })

    # ── Forecasting con Darts (ExponentialSmoothing) ──────────────────────────

    def _forecast_with_darts(self, df: pd.DataFrame, horizonte_meses: int,
                              nombre: str) -> pd.DataFrame:
        """
        Proyecta una serie temporal usando Darts (ExponentialSmoothing o NaiveDrift).
        Los intervalos de confianza se calculan con la volatilidad histórica.

        Returns:
            DataFrame con columnas: fecha, valor_proyectado, lower_bound, upper_bound
        """
        TimeSeries, ExponentialSmoothing, NaiveDrift = _import_darts()

        # Agregar a nivel mensual y rellenar huecos
        df_m = (
            df.copy()
            .assign(fecha=lambda x: pd.to_datetime(x["fecha"]).dt.to_period("M").dt.to_timestamp())
            .groupby("fecha", as_index=False)["valor"].sum()
            .set_index("fecha")
            .asfreq("MS", fill_value=0)
            .reset_index()
        )

        series = TimeSeries.from_dataframe(df_m, time_col="fecha", value_cols="valor", freq="MS")

        # ExponentialSmoothing necesita ≥2 ciclos estacionales; usar NaiveDrift como fallback
        try:
            model = ExponentialSmoothing()
            model.fit(series)
            modelo_nombre = "ExponentialSmoothing (Darts)"
        except Exception:
            model = NaiveDrift()
            model.fit(series)
            modelo_nombre = "NaiveDrift (Darts)"

        # Predicción puntual (modelos deterministas en Darts)
        pred = model.predict(horizonte_meses)
        pred_df = pred.pd_dataframe().reset_index()
        pred_df.columns = ["fecha", "valor_proyectado"]

        # Intervalos de confianza ±1.645σ (90%) basados en volatilidad histórica
        cv = df_m["valor"].std() / df_m["valor"].mean() if df_m["valor"].mean() != 0 else 0.15
        sigma = pred_df["valor_proyectado"] * cv
        pred_df["lower_bound"] = (pred_df["valor_proyectado"] - 1.645 * sigma).clip(lower=0)
        pred_df["upper_bound"] =  pred_df["valor_proyectado"] + 1.645 * sigma
        pred_df["modelo"] = modelo_nombre

        # Asegurar que las fechas sean Timestamps
        if hasattr(pred_df["fecha"].iloc[0], "to_timestamp"):
            pred_df["fecha"] = pred_df["fecha"].dt.to_timestamp()

        return pred_df.reset_index(drop=True)

    # ── Forecasting con Prophet ────────────────────────────────────────────────

    def _forecast_with_prophet(self, df: pd.DataFrame, horizonte_meses: int,
                                nombre: str) -> pd.DataFrame:
        """
        Proyecta una serie temporal usando Prophet (detecta estacionalidad).

        Returns:
            DataFrame con columnas: fecha, valor_proyectado, lower_bound, upper_bound
        """
        Prophet = _import_prophet()

        df_prophet = (
            df.copy()
            .assign(ds=lambda x: pd.to_datetime(x["fecha"]))
            .groupby("ds", as_index=False)["valor"].sum()
            .rename(columns={"valor": "y"})
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=False,
                daily_seasonality=False,
                interval_width=0.80,
                changepoint_prior_scale=0.05,
            )
            model.fit(df_prophet)

        future = model.make_future_dataframe(periods=horizonte_meses, freq="MS")
        forecast = model.predict(future)

        result = forecast[forecast["ds"] > df_prophet["ds"].max()][
            ["ds", "yhat", "yhat_lower", "yhat_upper"]
        ].copy()

        result.columns = ["fecha", "valor_proyectado", "lower_bound", "upper_bound"]
        result["modelo"] = "Prophet"
        result["valor_proyectado"] = result["valor_proyectado"].clip(lower=0)
        result["lower_bound"] = result["lower_bound"].clip(lower=0)
        result["upper_bound"] = result["upper_bound"].clip(lower=0)

        return result.reset_index(drop=True)

    # ── API pública ────────────────────────────────────────────────────────────

    def forecast_ingresos(self, horizonte_meses: int = 12) -> pd.DataFrame:
        """
        Proyecta ingresos usando Prophet (si hay ≥12 meses) o Darts.

        Returns:
            DataFrame con: fecha, valor_proyectado, lower_bound, upper_bound, modelo
        """
        if self._df_ingresos is None:
            raise RuntimeError("Ejecuta load_data() antes de forecast_ingresos()")

        n_obs = len(self._df_ingresos)
        logger.info(f"Forecasting ingresos | obs={n_obs} | horizonte={horizonte_meses}m")

        if n_obs >= 12:
            try:
                return self._forecast_with_prophet(self._df_ingresos, horizonte_meses, "ingresos")
            except Exception as e:
                logger.warning(f"Prophet falló ({e}), usando Darts")

        return self._forecast_with_darts(self._df_ingresos, horizonte_meses, "ingresos")

    def forecast_costos(self, horizonte_meses: int = 12) -> pd.DataFrame:
        """
        Proyecta costos usando Prophet (si hay ≥12 meses) o Darts.

        Returns:
            DataFrame con: fecha, valor_proyectado, lower_bound, upper_bound, modelo
        """
        if self._df_costos is None:
            # Fallback: estimar costos como 65% de ingresos proyectados
            logger.warning("Sin datos de costos: estimando como 65% de ingresos")
            df_ingresos_hist = self._df_ingresos.copy()
            df_ingresos_hist["valor"] *= 0.65
            self._df_costos = df_ingresos_hist

        n_obs = len(self._df_costos)
        logger.info(f"Forecasting costos | obs={n_obs} | horizonte={horizonte_meses}m")

        if n_obs >= 12:
            try:
                return self._forecast_with_prophet(self._df_costos, horizonte_meses, "costos")
            except Exception as e:
                logger.warning(f"Prophet falló ({e}), usando Darts")

        return self._forecast_with_darts(self._df_costos, horizonte_meses, "costos")

    def forecast_volatilidad(self, variable: str = "TIIE",
                              horizonte_meses: int = 12) -> pd.DataFrame:
        """
        Proyecta volatilidad futura de una variable macro usando GARCH(1,1).

        Args:
            variable: 'TIIE', 'USD_MXN', 'INPC', etc.
            horizonte_meses: Número de meses a proyectar

        Returns:
            DataFrame con: fecha, volatilidad_proyectada, horizonte
        """
        arch_model = _import_arch()

        df = None
        if self._df_variables_exogenas is not None:
            df = self._df_variables_exogenas[
                self._df_variables_exogenas["variable"] == variable
            ].copy()

        if df is None or len(df) < 8:
            logger.warning(f"Datos insuficientes para {variable}, usando serie dummy")
            dates = pd.date_range(end=pd.Timestamp.now(), periods=24, freq="MS")
            base = {"TIIE": 10.5, "USD_MXN": 17.2, "INPC": 4.8}.get(variable, 5.0)
            df = pd.DataFrame({
                "fecha": dates,
                "valor": base + np.cumsum(np.random.default_rng(7).normal(0, 0.12, 24))
            })

        df = df.sort_values("fecha").dropna()
        returns = df["valor"].pct_change().dropna() * 100

        try:
            am = arch_model(returns, vol="Garch", p=1, q=1, dist="normal")
            res = am.fit(disp="off", show_warning=False)
            forecasts = res.forecast(horizon=horizonte_meses, reindex=False)
            variance_forecast = forecasts.variance.iloc[-1].values
            vol_forecast = np.sqrt(variance_forecast)
        except Exception as e:
            logger.warning(f"GARCH falló ({e}), usando volatilidad histórica constante")
            vol_historica = returns.std()
            vol_forecast = np.full(horizonte_meses, vol_historica)

        last_date = pd.to_datetime(df["fecha"].iloc[-1])
        fechas_futuras = pd.date_range(start=last_date + pd.offsets.MonthBegin(1),
                                        periods=horizonte_meses, freq="MS")

        return pd.DataFrame({
            "fecha": fechas_futuras,
            "variable": variable,
            "volatilidad_proyectada": vol_forecast,
            "modelo": "GARCH(1,1)",
        })

    def get_estacionalidad(self) -> dict:
        """
        Detecta estacionalidad en los ingresos usando Prophet.

        Returns:
            dict con meses de mayor/menor actividad y factor de estacionalidad
        """
        if self._df_ingresos is None or len(self._df_ingresos) < 12:
            return {"detectada": False, "motivo": "Datos insuficientes (<12 meses)"}

        try:
            Prophet = _import_prophet()
            df_prophet = (
                self._df_ingresos.copy()
                .assign(ds=lambda x: pd.to_datetime(x["fecha"]))
                .groupby("ds", as_index=False)["valor"].sum()
                .rename(columns={"valor": "y"})
            )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = Prophet(yearly_seasonality=True, weekly_seasonality=False,
                                daily_seasonality=False)
                model.fit(df_prophet)

            future = model.make_future_dataframe(periods=12, freq="MS")
            forecast = model.predict(future)

            seasonal = forecast[["ds", "yearly"]].copy()
            seasonal["mes"] = seasonal["ds"].dt.month
            por_mes = seasonal.groupby("mes")["yearly"].mean()

            return {
                "detectada": True,
                "mes_pico": int(por_mes.idxmax()),
                "mes_valle": int(por_mes.idxmin()),
                "factor_pico": float(por_mes.max()),
                "factor_valle": float(por_mes.min()),
            }
        except Exception as e:
            return {"detectada": False, "motivo": str(e)}

    def run_all(self, horizonte_meses: int = 12) -> dict:
        """
        Ejecuta el pipeline completo del Escudo 1.

        Returns:
            dict con claves: ingresos_12m, costos_12m, volatilidad_tiie,
                             flujo_libre_12m, estacionalidad_detectada
        """
        logger.info(f"Escudo 1 - Radar: iniciando pipeline | horizonte={horizonte_meses}m")

        df_ingresos = self.forecast_ingresos(horizonte_meses)
        df_costos   = self.forecast_costos(horizonte_meses)
        df_vol      = self.forecast_volatilidad("TIIE", horizonte_meses)
        estacional  = self.get_estacionalidad()

        # Flujo libre proyectado = ingresos - costos
        df_flujo = df_ingresos[["fecha", "valor_proyectado"]].copy()
        df_flujo = df_flujo.rename(columns={"valor_proyectado": "ingresos"})
        df_flujo["costos"] = df_costos["valor_proyectado"].values
        df_flujo["flujo_libre"] = df_flujo["ingresos"] - df_flujo["costos"]
        df_flujo["flujo_acumulado"] = df_flujo["flujo_libre"].cumsum()

        logger.info("Escudo 1 completado exitosamente")

        return {
            "ingresos_12m": df_ingresos,
            "costos_12m": df_costos,
            "volatilidad_tiie": df_vol,
            "flujo_libre_12m": df_flujo,
            "estacionalidad_detectada": estacional,
            "horizonte_meses": horizonte_meses,
            "generado_en": datetime.now().isoformat(),
        }
