import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(page_title="Análisis Demográfico Mundial", layout="wide")
st.title("🌍 Dashboard Demográfico Mundial")
st.markdown("Visualiza y compara datos demográficos de todos los países usando la API pública [REST Countries](https://restcountries.com).")

# Cargar datos de la API REST Countries
@st.cache_data
def load_country_data():
    url = "https://restcountries.com/v3.1/all"
    response = requests.get(url)
    data = response.json()
    
    # Extraer datos relevantes
    country_data = []
    for country in data:
        try:
            name = country['name']['common']
            population = country.get('population', 0)
            area = country.get('area', None)
            region = country.get('region', 'Unknown')
            subregion = country.get('subregion', 'Unknown')
            density = population / area if area else None

            country_data.append({
                'País': name,
                'Población': population,
                'Área (km²)': area,
                'Región': region,
                'Subregión': subregion,
                'Densidad Poblacional': density
            })
        except Exception as e:
            continue
    
    return pd.DataFrame(country_data)

df = load_country_data()

# Sidebar para filtros
st.sidebar.header("Filtros Demográficos")
regiones = sorted(df['Región'].dropna().unique())
region_seleccionada = st.sidebar.multiselect("Selecciona región(es):", regiones, default=regiones)

df_filtrado = df[df['Región'].isin(region_seleccionada)]

# Mostrar tabla resumida
st.subheader("📋 Datos por país")
st.dataframe(df_filtrado.sort_values("Población", ascending=False), use_container_width=True)

# Gráfico de población por país
st.subheader("👥 Población Total por País")
fig1 = px.bar(df_filtrado.sort_values("Población", ascending=False).head(20),
              x='País', y='Población', color='Región',
              title='Top 20 países por población',
              labels={'Población': 'Habitantes'})
st.plotly_chart(fig1, use_container_width=True)

# Gráfico de densidad poblacional
st.subheader("🏘️ Densidad Poblacional por País")
top_density = df_filtrado[df_filtrado['Densidad Poblacional'].notnull()].sort_values("Densidad Poblacional", ascending=False).head(20)
fig2 = px.bar(top_density, x='País', y='Densidad Poblacional', color='Región',
              title='Top 20 países por densidad poblacional',
              labels={'Densidad Poblacional': 'Habitantes por km²'})
st.plotly_chart(fig2, use_container_width=True)

st.caption("Fuente de datos: [REST Countries API](https://restcountries.com)")
