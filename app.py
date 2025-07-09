import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
        "B25003_001E": "Total Viviendas",  # Total housing units
        "B25003_002E": "Viviendas Propias",  # Owner-occupied housing
        "B15003_022E": "Educación Universitaria",  # Bachelor's degree
        "B08303_001E": "Tiempo Promedio al Trabajo (min)",  # Mean travel time to work
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

# ============================================================================
# SESSION STATE MANAGEMENT
# ============================================================================

if 'selected_state' not in st.session_state:
    st.session_state.selected_state = None
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = 'overview'  # 'overview' or 'detail'

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
        
        # Calculate percentages for demographic composition
        df['% Blancos'] = (df['Blancos'] / df['Población Total'] * 100).round(2)
        df['% Afroamericanos'] = (df['Afroamericanos'] / df['Población Total'] * 100).round(2)
        df['% Asiáticos'] = (df['Asiáticos'] / df['Población Total'] * 100).round(2)
        df['% Haw/Pacific'] = (df['Haw/Pacific'] / df['Población Total'] * 100).round(2)
        df['% Viviendas Propias'] = (df['Viviendas Propias'] / df['Total Viviendas'] * 100).round(2)
        
        return df.sort_values('Estado')
        
    except Exception as e:
        st.error(f"❌ Error procesando datos: {str(e)}")
        return pd.DataFrame()

# ============================================================================
# UI FUNCTIONS
# ============================================================================

def show_state_selector(df: pd.DataFrame):
    """Show state selector and navigation controls"""
    st.markdown("### 🗺️ Selector de Estados")
    
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        selected_state = st.selectbox(
            "Selecciona un estado para ver información detallada:",
            options=['Todos los Estados'] + list(df['Estado'].unique()),
            index=0 if st.session_state.selected_state is None else 
                  list(df['Estado'].unique()).index(st.session_state.selected_state) + 1
        )
    
    with col2:
        if st.button("🔍 Ver Detalles", disabled=(selected_state == 'Todos los Estados')):
            st.session_state.selected_state = selected_state
            st.session_state.view_mode = 'detail'
            st.rerun()
    
    with col3:
        if st.button("📊 Vista General"):
            st.session_state.selected_state = None
            st.session_state.view_mode = 'overview'
            st.rerun()

def show_state_detail(df: pd.DataFrame, state_name: str):
    """Show detailed information for a specific state"""
    state_data = df[df['Estado'] == state_name].iloc[0]
    
    # Header with state name and navigation
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title(f"🏛️ {state_name}")
        st.markdown("Información demográfica detallada")
    
    with col2:
        if st.button("⬅️ Volver a Vista General"):
            st.session_state.selected_state = None
            st.session_state.view_mode = 'overview'
            st.rerun()
    
    # Quick state selector
    st.markdown("**Cambiar a otro estado:**")
    other_states = [s for s in df['Estado'].unique() if s != state_name]
    new_state = st.selectbox(
        "Seleccionar otro estado:",
        options=other_states,
        key="state_changer"
    )
    
    if st.button("🔄 Cambiar Estado"):
        st.session_state.selected_state = new_state
        st.rerun()
    
    st.markdown("---")
    
    # Key metrics for the state
    st.subheader("📊 Métricas Principales")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Población Total", 
            f"{int(state_data['Población Total']):,}",
            help="Población total del estado"
        )
    
    with col2:
        st.metric(
            "Ingreso Medio Anual", 
            f"${int(state_data['Ingreso Medio ($)']):,}",
            help="Ingreso medio por hogar"
        )
    
    with col3:
        st.metric(
            "Viviendas Propias", 
            f"{state_data['% Viviendas Propias']:.1f}%",
            help="Porcentaje de viviendas propias vs alquiladas"
        )
    
    with col4:
        st.metric(
            "Tiempo al Trabajo", 
            f"{int(state_data['Tiempo Promedio al Trabajo (min)']):.0f} min",
            help="Tiempo promedio de traslado al trabajo"
        )
    
    # Demographic composition
    st.subheader("🧬 Composición Demográfica")
    
    # Create pie chart for demographic composition
    demo_data = {
        'Blancos': state_data['% Blancos'],
        'Afroamericanos': state_data['% Afroamericanos'], 
        'Asiáticos': state_data['% Asiáticos'],
        'Haw/Pacific': state_data['% Haw/Pacific']
    }
    
    # Remove zero values for cleaner chart
    demo_data = {k: v for k, v in demo_data.items() if v > 0}
    
    fig_pie = px.pie(
        values=list(demo_data.values()),
        names=list(demo_data.keys()),
        title=f"Composición Racial en {state_name}",
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    
    st.plotly_chart(fig_pie, use_container_width=True)
    
    # Comparison with national averages
    st.subheader("📈 Comparación con Promedios Nacionales")
    
    national_avg_income = df['Ingreso Medio ($)'].mean()
    national_avg_homeowner = df['% Viviendas Propias'].mean()
    
    comparison_data = {
        'Métrica': ['Ingreso Medio ($)', 'Viviendas Propias (%)'],
        'Estado': [int(state_data['Ingreso Medio ($)']), state_data['% Viviendas Propias']],
        'Promedio Nacional': [int(national_avg_income), national_avg_homeowner]
    }
    
    fig_comparison = px.bar(
        pd.DataFrame(comparison_data),
        x='Métrica',
        y=['Estado', 'Promedio Nacional'],
        title=f"Comparación: {state_name} vs Promedio Nacional",
        barmode='group',
        color_discrete_sequence=['#FF6B6B', '#4ECDC4']
    )
    
    st.plotly_chart(fig_comparison, use_container_width=True)
    
    # Detailed data table
    st.subheader("📋 Datos Detallados")
    
    detail_data = {
        'Indicador': [
            'Población Total',
            'Ingreso Medio ($)',
            'Total Viviendas', 
            'Viviendas Propias',
            'Población Blanca',
            'Población Afroamericana',
            'Población Asiática',
            'Población Haw/Pacific',
            'Educación Universitaria',
            'Tiempo Promedio al Trabajo (min)'
        ],
        'Valor Absoluto': [
            f"{int(state_data['Población Total']):,}",
            f"${int(state_data['Ingreso Medio ($)']):,}",
            f"{int(state_data['Total Viviendas']):,}",
            f"{int(state_data['Viviendas Propias']):,}",
            f"{int(state_data['Blancos']):,}",
            f"{int(state_data['Afroamericanos']):,}",
            f"{int(state_data['Asiáticos']):,}",
            f"{int(state_data['Haw/Pacific']):,}",
            f"{int(state_data['Educación Universitaria']):,}",
            f"{int(state_data['Tiempo Promedio al Trabajo (min)']):.0f} min"
        ],
        'Porcentaje': [
            "100%",
            "-",
            "100%",
            f"{state_data['% Viviendas Propias']:.1f}%",
            f"{state_data['% Blancos']:.1f}%",
            f"{state_data['% Afroamericanos']:.1f}%",
            f"{state_data['% Asiáticos']:.1f}%",
            f"{state_data['% Haw/Pacific']:.1f}%",
            f"{(state_data['Educación Universitaria'] / state_data['Población Total'] * 100):.1f}%",
            "-"
        ]
    }
    
    st.dataframe(pd.DataFrame(detail_data), use_container_width=True)

def show_overview(df: pd.DataFrame):
    """Show overview of all states"""
    st.title("🇺🇸 Dashboard Demográfico de Estados Unidos")
    st.markdown("Datos en tiempo real desde la API del **US Census Bureau (ACS 5-Year Survey)**")
    
    # Display data info
    st.success(f"✅ Datos cargados exitosamente: {len(df)} estados")
    
    # Métricas globales
    st.subheader("📊 Métricas Generales")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_pop = df['Población Total'].sum()
        col1.metric("Población Total (50 estados)", f"{total_pop:,}")
    
    with col2:
        avg_income = df['Ingreso Medio ($)'].mean()
        col2.metric("Ingreso Medio Promedio", f"${int(avg_income):,}")
    
    with col3:
        avg_homeowner = df['% Viviendas Propias'].mean()
        col3.metric("Promedio Viviendas Propias", f"{avg_homeowner:.1f}%")
    
    with col4:
        col4.metric("Estados con Datos", len(df))
    
    # Gráfico de población por estado
    st.subheader("👥 Población Total por Estado")
    fig_pop = px.bar(
        df.sort_values("Población Total", ascending=False).head(15),
        x="Estado", 
        y="Población Total",
        title="Top 15 Estados por Población",
        text_auto=True,
        color="Población Total",
        color_continuous_scale="viridis"
    )
    fig_pop.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_pop, use_container_width=True)
    
    # Gráfico de ingreso medio
    st.subheader("💰 Ingreso Medio por Estado")
    fig_income = px.bar(
        df.sort_values("Ingreso Medio ($)", ascending=False).head(15),
        x="Estado", 
        y="Ingreso Medio ($)",
        title="Top 15 Estados por Ingreso Medio",
        text_auto=True,
        color="Ingreso Medio ($)",
        color_continuous_scale="plasma"
    )
    fig_income.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_income, use_container_width=True)
    
    # Distribución racial por estado (stacked bar)
    st.subheader("🧬 Composición Racial por Estado (muestra)")
    # Show only top 10 by population for readability
    top_states = df.sort_values("Población Total", ascending=False).head(10)
    racial_columns = ["Blancos", "Afroamericanos", "Asiáticos", "Haw/Pacific"]
    fig_race = px.bar(
        top_states, 
        x="Estado", 
        y=racial_columns,
        title="Distribución racial - Top 10 Estados por Población",
        labels={"value": "Población", "variable": "Grupo Racial"},
        barmode="stack"
    )
    fig_race.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_race, use_container_width=True)

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
    
    st.markdown("---")
    st.markdown("### 🗺️ Navegación")
    
    if st.session_state.view_mode == 'detail':
        st.info(f"**Vista actual:** Detalles de {st.session_state.selected_state}")
    else:
        st.info("**Vista actual:** Vista General")

# ============================================================================
# MAIN APPLICATION
# ============================================================================

# Load data
df = load_census_data()

if df.empty:
    st.warning("⚠️ No hay datos disponibles. Verifique la conexión a internet y la configuración de la API.")
    st.stop()

# Show state selector
show_state_selector(df)

st.markdown("---")

# Show content based on current view mode
if st.session_state.view_mode == 'detail' and st.session_state.selected_state:
    show_state_detail(df, st.session_state.selected_state)
else:
    show_overview(df)

# Footer
st.markdown("---")
st.caption("Fuente: [US Census Bureau - ACS 5-Year API](https://www.census.gov/data/developers.html)")
st.caption(f"Configuración API: {API_CONFIG['base_url']}")
