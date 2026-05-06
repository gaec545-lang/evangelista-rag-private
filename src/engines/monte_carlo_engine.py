import numpy as np
import pandas as pd
from typing import Dict, List, Callable, Optional, Any
from src.configuration_manager import ConfigurationManager
from src.excel_connector import ExcelConnector
from src.database_connector import DatabaseConnector, DatabaseConnectionError, DatabaseQueryError
import logging

logger = logging.getLogger(__name__)


class UniversalMonteCarloEngine:
    """
    Motor de simulación Monte Carlo configurable
    
    Ejemplo:
        config = ConfigurationManager('templates/alimentos.yaml', 'clients/test_pasteleria_config.yaml')
        engine = UniversalMonteCarloEngine(config)
        engine.load_historical_data()
        engine.setup_simulation()
        results = engine.run()
        stats = engine.get_statistics()
    """
    
    def __init__(self, config: ConfigurationManager):
       
        self.config = config
        self.historical_data = {}
        self.variables_config = []
        self.model_function = None
        self.results = None
        
        # Validar configuración
        is_valid, errors = config.validate()
        if not is_valid:
            raise ValueError(f"❌ Configuración inválida:\n" + "\n".join(errors))
    
    def load_historical_data(self):
        """
        Carga datos históricos desde fuentes configuradas
        
        Prioridad de fuentes:
        1. Database (production) - DatabaseConnector
        2. Excel (legacy/demos) - ExcelConnector (deprecado)
        """
        data_sources = self.config.get('data_sources', [])
        
        if not data_sources:
            print("⚠️  No hay data_sources configuradas. Usando precios actuales.")
            return
        
        for source in data_sources:
            source_type = source.get('type')
            
            if source_type == 'database':
                self._load_from_database(source)
            
            elif source_type == 'excel':
                logger.warning(
                    "⚠️  ExcelConnector está deprecado para producción. "
                    "Migrar a 'type: database' en configuración."
                )
                self._load_from_excel(source)
            
            else:
                print(f"⚠️  Tipo de source no soportado: {source_type}")

    def _load_from_database(self, source_config: dict):
        """
        Carga datos desde Data Mesh via DatabaseConnector
        """
        # Extraer credenciales de conexión
        engine = source_config.get('engine', 'postgresql')
        host = source_config.get('host')
        port = source_config.get('port')
        database = source_config.get('database')
        username = source_config.get('username')
        password = source_config.get('password')
        
        # Validar configuración mínima
        required = ['host', 'database', 'username', 'password']
        missing = [k for k in required if not source_config.get(k)]
        
        if missing:
            print(f"❌ Configuración incompleta en data_source. Faltan: {missing}")
            return
        
        try:
            # Inicializar conector
            connector = DatabaseConnector(
                engine=engine,
                host=host,
                database=database,
                username=username,
                password=password,
                port=port
            )
            
            # Validar conexión antes de queries
            is_valid, message = connector.validate_connection()
            if not is_valid:
                print(f"❌ {message}")
                return
            
            # Iterar sobre tablas configuradas
            tables_config = source_config.get('tables', [])
            
            for table_config in tables_config:
                table = table_config.get('table')
                date_column = table_config.get('date_column')
                value_column = table_config.get('value_column')
                variable_name = table_config.get('maps_to_variable')
                filters = table_config.get('filters', {})
                start_date = table_config.get('start_date')
                end_date = table_config.get('end_date')
                
                # Validar configuración de tabla
                if not all([table, date_column, value_column, variable_name]):
                    print(
                        f"⚠️  Configuración incompleta en tabla. "
                        f"Requiere: table, date_column, value_column, maps_to_variable"
                    )
                    continue
                
                try:
                    # Extraer serie temporal
                    df = connector.query_time_series(
                        table=table,
                        date_column=date_column,
                        value_column=value_column,
                        filters=filters,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    if df.empty:
                        print(
                            f"⚠️  No hay datos para {variable_name} en tabla {table}. "
                            f"Filtros: {filters}"
                        )
                        continue
                    
                    # Guardar en historical_data
                    self.historical_data[variable_name] = df[['fecha', 'valor']].copy()
                    
                    print(
                        f"✅ Datos cargados desde DB: {variable_name} "
                        f"({len(df)} registros de {table})"
                    )
                    
                except DatabaseQueryError as e:
                    print(f"❌ Error en query para {variable_name}: {e}")
                    continue
            
            # Cerrar conexión
            connector.close()
            
        except DatabaseConnectionError as e:
            print(f"❌ Error de conexión a Data Mesh: {e}")
            print("💡 Verifica: credenciales, firewall, servicio de BD activo")
            return
        
        except Exception as e:
            print(f"❌ Error inesperado al cargar desde database: {e}")
            return
    
    def _load_from_excel(self, source_config: dict):
        """Carga datos desde Excel"""
        path = source_config['path']
        
        try:
            connector = ExcelConnector(path)
        except FileNotFoundError:
            print(f"⚠️  Archivo no encontrado: {path}. Continuando sin datos históricos.")
            return
        
        sheets_config = source_config.get('sheets', [])
        
        for sheet_config in sheets_config:
            sheet_name = sheet_config['name']
            date_col = sheet_config['date_column']
            value_col = sheet_config['value_column']
            variable_name = sheet_config['maps_to_variable']
            
            try:
                df = connector.read_sheet(sheet_name)
                
                # Validar columnas
                if date_col not in df.columns:
                    print(f"⚠️  Columna '{date_col}' no existe en hoja '{sheet_name}'")
                    continue
                
                if value_col not in df.columns:
                    print(f"⚠️  Columna '{value_col}' no existe en hoja '{sheet_name}'")
                    continue
                
                # Guardar
                self.historical_data[variable_name] = df[[date_col, value_col]].copy()
                self.historical_data[variable_name].columns = ['fecha', 'valor']
                
                print(f"✅ Datos cargados: {variable_name} ({len(df)} filas)")
                
            except Exception as e:
                print(f"⚠️  Error al cargar hoja '{sheet_name}': {e}")
    
    def setup_simulation(self):
        """
        Configura variables y modelo de negocio
        """
        print("\n📋 Configurando simulación...")
        
        # 1. Configurar variables
        variables = self.config.get_variables()
        
        for var in variables:
            var_name = var['name']
            
            # Obtener configuración de distribución
            dist_config = self.config.get_distribution_config(var_name)
            
            # Calcular parámetros
            if var_name in self.historical_data:
                params = self._calculate_distribution_params(var_name, dist_config)
                print(f"   ✅ {var_name}: {dist_config['type']} (desde datos históricos)")
            else:
                params = self._get_fallback_params(var_name, dist_config)
                print(f"   ✅ {var_name}: {dist_config['type']} (fallback)")
            
            self.variables_config.append({
                'name': var_name,
                'distribution': dist_config['type'],
                'params': params
            })
        
        # 2. Cargar modelo de negocio
        model_code = self.config.get_business_model()
        
        # Ejecutar código para definir función
        namespace = {}
        exec(model_code, namespace)
        
        # Buscar función que empiece con "modelo_"
        for name, obj in namespace.items():
            if name.startswith('modelo_') and callable(obj):
                self.model_function = obj
                print(f"   ✅ Modelo de negocio: {name}")
                break
        
        if not self.model_function:
            raise ValueError("❌ No se encontró función de modelo en template")
        
        print("✅ Configuración completa\n")
    
    def _calculate_distribution_params(self, variable_name: str, dist_config: dict) -> dict:
        """Calcula parámetros desde datos históricos"""
        df = self.historical_data[variable_name]
        values = df['valor'].dropna()
        
        dist_type = dist_config['type']
        
        if dist_type == 'normal':
            return {
                'mean': float(values.mean()),
                'std': float(values.std())
            }
        
        elif dist_type == 'triangular':
            return {
                'min': float(values.min()),
                'mode': float(values.median()),
                'max': float(values.max())
            }
        
        elif dist_type == 'uniform':
            return {
                'min': float(values.min()),
                'max': float(values.max())
            }
        
        else:
            raise ValueError(f"❌ Distribución no soportada: {dist_type}")
    
    def _get_fallback_params(self, variable_name: str, dist_config: dict) -> dict:
        """Obtiene parámetros de fallback"""
        fallback = dist_config.get('fallback', {})
        current_prices = self.config.get('current_prices', {})
        current_value = current_prices.get(variable_name, 100)
        
        dist_type = dist_config['type']
        
        if dist_type == 'normal':
            mean = fallback.get('mean', current_value)
            std = fallback.get('std', current_value * 0.1)
            return {'mean': mean, 'std': std}
        
        elif dist_type == 'triangular':
            min_pct = fallback.get('min_pct', -0.10)
            mode_pct = fallback.get('mode_pct', 0.00)
            max_pct = fallback.get('max_pct', 0.15)
            
            return {
                'min': current_value * (1 + min_pct),
                'mode': current_value * (1 + mode_pct),
                'max': current_value * (1 + max_pct)
            }
        
        else:
            raise ValueError(f"❌ No hay fallback para distribución: {dist_type}")
    
    def run(self) -> pd.DataFrame:
        """
        Ejecuta simulación Monte Carlo
        
        Returns:
            DataFrame con resultados
        """
        n_sims = self.config.get('simulation.n_simulations', 10000)
        seed = self.config.get('simulation.seed')
        
        if seed:
            np.random.seed(seed)
        
        print(f"🎲 Ejecutando {n_sims:,} simulaciones...\n")
        
        # Generar samples para cada variable
        samples = {}
        for var_config in self.variables_config:
            name = var_config['name']
            dist = var_config['distribution']
            params = var_config['params']
            
            if dist == 'normal':
                samples[name] = np.random.normal(
                    params['mean'],
                    params['std'],
                    n_sims
                )
            
            elif dist == 'triangular':
                samples[name] = np.random.triangular(
                    params['min'],
                    params['mode'],
                    params['max'],
                    n_sims
                )
            
            elif dist == 'uniform':
                samples[name] = np.random.uniform(
                    params['min'],
                    params['max'],
                    n_sims
                )
        
        # Crear DataFrame
        df_samples = pd.DataFrame(samples)
        
        # Ejecutar modelo
        outcomes = []
        business_params = self.config.get('business_parameters')
        
        for idx, row in df_samples.iterrows():
            variables = row.to_dict()
            outcome = self.model_function(variables, business_params)
            outcomes.append(outcome)
        
        df_samples['outcome'] = outcomes
        df_samples['simulation_id'] = range(len(df_samples))
        
        self.results = df_samples
        
        print("✅ Simulación completada\n")
        
        return df_samples
    
    def get_statistics(self) -> Dict[str, float]:
        """Calcula estadísticas de resultados"""
        if self.results is None:
            raise RuntimeError("❌ Debes ejecutar run() primero")
        
        outcome = self.results['outcome']
        
        stats = {
            'mean': float(outcome.mean()),
            'median': float(outcome.median()),
            'std': float(outcome.std()),
            'min': float(outcome.min()),
            'max': float(outcome.max()),
            'p10': float(outcome.quantile(0.10)),
            'p25': float(outcome.quantile(0.25)),
            'p50': float(outcome.quantile(0.50)),
            'p75': float(outcome.quantile(0.75)),
            'p90': float(outcome.quantile(0.90)),
            'p95': float(outcome.quantile(0.95)),
            'p99': float(outcome.quantile(0.99)),
            'prob_loss': float((outcome < 0).mean()),
            'var_95': float(outcome.quantile(0.05)),
            'cvar_95': float(outcome[outcome <= outcome.quantile(0.05)].mean())
        }
        
        return stats
    
    def sensitivity_analysis(self) -> pd.DataFrame:
        """Análisis de sensibilidad simple"""
        if self.results is None:
            raise RuntimeError("❌ Debes ejecutar run() primero")
        
        correlations = []
        
        for var_config in self.variables_config:
            var_name = var_config['name']
            corr = self.results[var_name].corr(self.results['outcome'])
            
            correlations.append({
                'variable': var_name,
                'correlation': abs(corr),
                'importance': abs(corr) ** 2  # R-squared aproximado
            })
        
        df_sens = pd.DataFrame(correlations)
        df_sens = df_sens.sort_values('importance', ascending=False)
        df_sens = df_sens.reset_index(drop=True)
        
        return df_sens

    def evaluate_triggers(self, stats: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Evalúa los resultados estadísticos contra los umbrales de negocio (Decision Intelligence).
        """
        # Validar input
        if not stats:
            raise ValueError("❌ stats no puede estar vacío. Ejecutar get_statistics() primero.")
        
        required_keys = ['prob_loss', 'mean', 'std', 'p10']
        missing = [k for k in required_keys if k not in stats]
        if missing:
            raise ValueError(f"❌ stats incompleto. Faltan claves: {missing}")
        
        # Extraer thresholds de configuración
        thresholds = self.config.get('thresholds', {})
        
        if not thresholds:
            logger.warning(
                "⚠️  No hay 'thresholds' configurados en YAML. "
                "Usando valores default conservadores."
            )
            # Defaults conservadores si no hay configuración
            thresholds = {
                'critical_loss_prob': 0.20,  # 20% default
                'high_volatility': 0.30,      # 30% default
                'margin_protection': 0.05     # 5% buffer default
            }
        
        alerts: List[Dict[str, Any]] = []
        
        # ═══════════════════════════════════════════════════════════════
        # REGLA 1: RIESGO DE PÉRDIDA (Probabilidad vs Umbral Crítico)
        # ═══════════════════════════════════════════════════════════════
        prob_loss = stats['prob_loss']
        critical_threshold = thresholds.get('critical_loss_prob', 0.25)
        
        if prob_loss > critical_threshold:
            excess_pct = ((prob_loss - critical_threshold) / critical_threshold) * 100
            
            if prob_loss > critical_threshold * 1.5:
                nivel = "CRÍTICO"
                mensaje = (
                    f"⛔ RIESGO SISTÉMICO: La probabilidad de pérdida ({prob_loss:.1%}) "
                    f"supera en {excess_pct:.0f}% el umbral crítico del negocio ({critical_threshold:.1%})."
                )
            else:
                nivel = "ALTO"
                mensaje = (
                    f"⚠️  ALERTA DE RIESGO: La probabilidad de pérdida ({prob_loss:.1%}) "
                    f"supera el umbral crítico ({critical_threshold:.1%}) por {excess_pct:.0f}%."
                )
            
            alerts.append({
                'nivel': nivel,
                'metrica': 'prob_loss',
                'valor_actual': prob_loss,
                'umbral_permitido': critical_threshold,
                'mensaje': mensaje,
                'timestamp': pd.Timestamp.now().isoformat()
            })
        
        # ═══════════════════════════════════════════════════════════════
        # REGLA 2: VOLATILIDAD OPERATIVA (Coeficiente de Variación)
        # ═══════════════════════════════════════════════════════════════
        mean = stats['mean']
        std = stats['std']
        
        if mean != 0:
            coef_variacion = abs(std / mean)
            volatility_threshold = thresholds.get('high_volatility', 0.35)
            
            if coef_variacion > volatility_threshold:
                excess_pct = ((coef_variacion - volatility_threshold) / volatility_threshold) * 100
                
                alerts.append({
                    'nivel': "ALTO",
                    'metrica': 'coef_variacion',
                    'valor_actual': coef_variacion,
                    'umbral_permitido': volatility_threshold,
                    'mensaje': (
                        f"📊 VOLATILIDAD ELEVADA: El coeficiente de variación ({coef_variacion:.1%}) "
                        f"supera el umbral de estabilidad ({volatility_threshold:.1%}) por {excess_pct:.0f}%."
                    ),
                    'timestamp': pd.Timestamp.now().isoformat()
                })
        
        # ═══════════════════════════════════════════════════════════════
        # REGLA 3: PROTECCIÓN DE MARGEN (P10 Negativo o Límite Crítico)
        # ═══════════════════════════════════════════════════════════════
        p10 = stats['p10']
        margin_protection = thresholds.get('margin_protection', 0.05)
        
        if p10 < 0:
            alerts.append({
                'nivel': "CRÍTICO",
                'metrica': 'p10',
                'valor_actual': p10,
                'umbral_permitido': 0.0,
                'mensaje': f"🔴 EXPOSICIÓN FINANCIERA: El percentil P10 (${p10:,.0f}) es negativo. Riesgo de pérdidas directas.",
                'timestamp': pd.Timestamp.now().isoformat()
            })
        elif mean > 0:
            margin_ratio = p10 / mean
            if margin_ratio < margin_protection:
                alerts.append({
                    'nivel': "MEDIO",
                    'metrica': 'margin_ratio',
                    'valor_actual': margin_ratio,
                    'umbral_permitido': margin_protection,
                    'mensaje': (
                        f"⚠️  MARGEN REDUCIDO: El P10 representa solo {margin_ratio:.1%} de la ganancia esperada. "
                        f"Umbral de protección: {margin_protection:.1%}."
                    ),
                    'timestamp': pd.Timestamp.now().isoformat()
                })
        
        return alerts