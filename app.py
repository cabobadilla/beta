import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import os
from typing import Dict, List, Optional

# ============================================================================
# GLOBAL CONFIGURATION - Streamlit Cloud Compatible
# ============================================================================

@st.cache_data
def get_api_config() -> Dict:
    """
    Get API configuration from Streamlit secrets or environment variables.
    This function manages global API settings for Streamlit Cloud deployment.
    """
    try:
        # Try to get from Streamlit secrets first (preferred for Streamlit Cloud)
        if hasattr(st, 'secrets') and 'census_api' in st.secrets:
            return {
                'base_url': st.secrets.census_api.get('base_url', 'https://api.census.gov/data/2022/acs/acs5'),
                'year': st.secrets.census_api.get('year', '2022'),
                'dataset': st.secrets.census_api.get('dataset', 'acs/acs5'),
                'timeout': st.secrets.census_api.get('timeout', 30),
                'retry_attempts': st.secrets.census_api.get('retry_attempts', 3)
            }
    except Exception:
        pass
    
    # Fallback to environment variables or defaults
    return {
        'base_url': os.getenv('CENSUS_BASE_URL', 'https://api.census.gov/data/2022/acs/acs5'),
        'year': os.getenv('CENSUS_YEAR', '2022'),
        'dataset': os.getenv('CENSUS_DATASET', 'acs/acs5'),
        'timeout': int(os.getenv('API_TIMEOUT', '30')),
        'retry_attempts': int(os.getenv('API_RETRY_ATTEMPTS', '3'))
    }

@st.cache_data
def get_census_variables() -> Dict[str, str]:
    """
    Define Census API variables in a global, configurable way.
    """
    return {
        "NAME": "Estado",
        "B01003_001E": "Población Total",  # Total population
        "B19013_001E": "Ingreso Medio ($)",  # Median household income
        "B02001_002E": "Blancos",  # White alone
        "B02001_003E": "Afroamericanos",  # Black or African American alone
        "B02001_005E": "Asiáticos",  # Asian alone
        "B02001_006E": "Haw/Pacific",  # Native Hawaiian and Other Pacific Islander alone
    }

# Initialize global configuration
API_CONFIG = get_api_config()
CENSUS_VARIABLES = get_census_variables()

# ============================================================================
# STREAMLIT APP CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Demografía USA - Census API", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🇺🇸 Dashboard Demográfico de Estados Unidos")
st.markdown("Datos en tiempo real desde la API del **US Census Bureau (ACS 5-Year Survey)**")

# ============================================================================
# API FUNCTIONS WITH IMPROVED ERROR HANDLING
# ============================================================================

def make_census_request(url: str) -> Optional[List]:
    """
    Make a request to the Census API with retry logic and proper error handling.
    """
    for attempt in range(API_CONFIG['retry_attempts']):
        try:
            response = requests.get(url, timeout=API_CONFIG['timeout'])
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            if attempt == API_CONFIG['retry_attempts'] - 1:
                st.error(f"⏱️ Timeout al conectar con Census API después de {API_CONFIG['retry_attempts']} intentos")
                return None
            st.warning(f"Intento {attempt + 1} falló, reintentando...")
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Error de conexión con Census API: {str(e)}")
            return None
        except Exception as e:
            st.error(f"❌ Error inesperado: {str(e)}")
            return None
    return None

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_census_data() -> pd.DataFrame:
    """
    Load demographic data from US Census API with improved error handling and caching.
    """
    # Build API request URL
    variables = list(CENSUS_VARIABLES.keys())
    var_str = ",".join(variables)
    url = f"{API_CONFIG['base_url']}?get={var_str}&for=state:*"
    
    # Show loading message
    with st.spinner('🔄 Cargando datos desde US Census API...'):
        data = make_census_request(url)
    
    if not data or len(data) < 2:
        st.error("❌ No se pudieron cargar los datos del Census API")
        return pd.DataFrame()
    
    # Process data
    try:
        headers = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=headers)
        
        # Convert numeric columns
        numeric_cols = [col for col in headers[1:-1] if col != 'NAME']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # Rename columns using our mapping
        df = df.rename(columns=CENSUS_VARIABLES)
        
        # Remove any rows with all NaN values
        df = df.dropna(subset=[col for col in df.columns if col != 'Estado'])
        
        return df
        
    except Exception as e:
        st.error(f"❌ Error procesando datos: {str(e)}")
        return pd.DataFrame()

# ============================================================================
# SIDEBAR CONFIGURATION
# ============================================================================

with st.sidebar:
    st.header("⚙️ Configuración")
    st.info(f"**API Endpoint:** {API_CONFIG['base_url']}")
    st.info(f"**Año de datos:** {API_CONFIG['year']}")
    
    if st.button("🔄 Actualizar Datos"):
        st.cache_data.clear()
        st.rerun()

# ============================================================================
# MAIN APPLICATION
# ============================================================================

# Load data
df = load_census_data()

if df.empty:
    st.warning("⚠️ No hay datos disponibles. Verifique la conexión a internet y la configuración de la API.")
    st.stop()

# Display data info
st.success(f"✅ Datos cargados exitosamente: {len(df)} estados")

# Métricas globales
st.subheader("📊 Métricas Generales")
col1, col2, col3 = st.columns(3)

with col1:
    total_pop = df['Población Total'].sum()
    col1.metric("Población Total (50 estados)", f"{total_pop:,}")

with col2:
    avg_income = df['Ingreso Medio ($)'].mean()
    col2.metric("Ingreso Medio Promedio", f"${int(avg_income):,}")

with col3:
    col3.metric("Estados con Datos", len(df))

# Gráfico de población por estado
st.subheader("👥 Población Total por Estado")
fig_pop = px.bar(
    df.sort_values("Población Total", ascending=False),
    x="Estado", 
    y="Población Total",
    title="Población por estado",
    text_auto=True
)
fig_pop.update_layout(xaxis_tickangle=-45)
st.plotly_chart(fig_pop, use_container_width=True)

# Gráfico de ingreso medio
st.subheader("💰 Ingreso Medio por Estado")
fig_income = px.bar(
    df.sort_values("Ingreso Medio ($)", ascending=False),
    x="Estado", 
    y="Ingreso Medio ($)",
    title="Ingreso medio por hogar",
    text_auto=True,
    color="Ingreso Medio ($)",
    color_continuous_scale="viridis"
)
fig_income.update_layout(xaxis_tickangle=-45)
st.plotly_chart(fig_income, use_container_width=True)

# Distribución racial por estado (stacked bar)
st.subheader("🧬 Composición Racial por Estado (aproximada)")
racial_columns = ["Blancos", "Afroamericanos", "Asiáticos", "Haw/Pacific"]
fig_race = px.bar(
    df, 
    x="Estado", 
    y=racial_columns,
    title="Distribución racial por estado",
    labels={"value": "Población", "variable": "Grupo Racial"},
    barmode="stack"
)
fig_race.update_layout(xaxis_tickangle=-45)
st.plotly_chart(fig_race, use_container_width=True)

# Footer
st.markdown("---")
st.caption("Fuente: [US Census Bureau - ACS 5-Year API](https://www.census.gov/data/developers.html)")
st.caption(f"Configuración API: {API_CONFIG['base_url']}")
