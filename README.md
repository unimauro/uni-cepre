# UNI CEPRE Results Scraper

Script para descargar los resultados del examen de admisión UNI CEPRE y realizar análisis estadísticos.

## Características

- Descarga todos los resultados desde el sitio web oficial
- Guarda los datos en formato CSV
- Importa los datos a una base de datos SQLite
- Genera análisis automáticos:
  - Total de postulantes e ingresantes
  - Estadísticas por especialidad (máximo, mínimo, promedio, número de ingresantes)
  - Estadísticas por modalidad
  - Top 10 puntajes más altos
- **Notebook de Google Colab** para análisis interactivo con visualizaciones

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

```bash
python scraper.py
```

El script generará:
- `resultados_uni.csv`: Archivo CSV con todos los resultados
- `resultados_uni.db`: Base de datos SQLite para análisis

## Estructura de Datos

Los datos incluyen las siguientes columnas:
- `codigo`: Código del postulante
- `nombre_completo`: Nombre completo del postulante
- `modalidad`: Modalidad de ingreso
- `puntaje_final`: Puntaje final obtenido
- `especialidad`: Especialidad a la que postuló

## Análisis con Google Colab

Para un análisis interactivo con visualizaciones, usa el notebook de Google Colab:

1. Abre Google Colab: https://colab.research.google.com/
2. Sube el archivo `analisis_resultados_uni.ipynb` o abre directamente desde GitHub
3. Sube el archivo `resultados_uni.csv` cuando se te solicite
4. Ejecuta todas las celdas para ver:
   - Estadísticas generales
   - Visualizaciones de distribución de puntajes
   - Análisis por especialidad y modalidad
   - Top 10 puntajes más altos
   - Análisis por rangos de puntaje
   - Búsqueda personalizada por código o nombre
   - Exportación de resultados a CSV

El notebook incluye gráficos interactivos y análisis detallados que facilitan la exploración de los datos.

## Análisis con SQLite

Puedes conectarte a la base de datos SQLite para realizar consultas personalizadas:

```bash
sqlite3 resultados_uni.db
```

Ejemplos de consultas:

```sql
-- Ver todas las especialidades
SELECT DISTINCT especialidad FROM resultados;

-- Ver estadísticas por especialidad
SELECT 
    especialidad,
    COUNT(*) as total,
    MAX(puntaje_final) as maximo,
    MIN(puntaje_final) as minimo,
    AVG(puntaje_final) as promedio
FROM resultados
GROUP BY especialidad;

-- Ver número de ingresantes por especialidad
SELECT 
    especialidad,
    COUNT(*) as ingresantes
FROM resultados
WHERE puntaje_final > 0
GROUP BY especialidad
ORDER BY ingresantes DESC;
```
