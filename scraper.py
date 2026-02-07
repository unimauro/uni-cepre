#!/usr/bin/env python3
"""
Script to scrape UNI CEPRE admission exam results and save to CSV and SQLite database.
"""

import requests
import json
import csv
import sqlite3
import re
import html
from typing import List, Dict
import sys

BASE_URL = "https://puntajes.admision.uni.edu.pe/cepre/resultados-finales/"


def get_page_content(url: str) -> str:
    """Fetch page content."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching page: {e}")
        sys.exit(1)


def decode_html_entities(text: str) -> str:
    """Decode HTML entities to proper UTF-8 characters."""
    import html
    # First decode HTML entities like &quot; to "
    text = html.unescape(text)
    # Handle any remaining encoding issues
    try:
        # If text was incorrectly decoded, try to fix it
        if 'Ã' in text or 'Ã©' in text:
            # This might be a double-encoding issue
            text = text.encode('latin-1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    return text


def extract_json_data(html_content: str) -> List[Dict[str, str]]:
    """Extract JSON data embedded in HTML."""
    results = []
    
    # The data is embedded as HTML-escaped JSON using &quot; instead of "
    # Format: [[0,{&quot;codigo&quot;:[0,&quot;...&quot;],&quot;nombres&quot;:[0,&quot;...&quot;],...}], ...]
    print("Extracting data using regex...")
    
    # Extract all records using regex patterns (handle HTML-escaped quotes)
    # Pattern for codigo: &quot;codigo&quot;:[0,&quot;VALUE&quot;]
    codigo_matches = re.findall(r'&quot;codigo&quot;:\[0,&quot;([^&]+)&quot;\]', html_content)
    nombres_matches = re.findall(r'&quot;nombres&quot;:\[0,&quot;([^&]+)&quot;\]', html_content)
    # Pattern for puntaje_final: &quot;puntaje_final&quot;:[0,NUMBER]
    puntaje_matches = re.findall(r'&quot;puntaje_final&quot;:\[0,([0-9.]+)\]', html_content)
    modalidad_matches = re.findall(r'&quot;modalidad&quot;:\[0,&quot;([^&]+)&quot;\]', html_content)
    # Handle ingreso which can be null or a string
    # Pattern: &quot;ingreso&quot;:[0,&quot;VALUE&quot;] or &quot;ingreso&quot;:[0,null]
    ingreso_matches = re.findall(r'&quot;ingreso&quot;:\[0,(?:&quot;([^&]+)&quot;|null)\]', html_content)
    
    print(f"Found: {len(codigo_matches)} codigos, {len(nombres_matches)} nombres, {len(puntaje_matches)} puntajes, {len(modalidad_matches)} modalidades, {len(ingreso_matches)} ingresos")
    
    # Match records by position - they should be in order
    max_len = len(codigo_matches)
    
    if max_len == 0:
        # Try alternative pattern without HTML escaping (in case it's already unescaped)
        print("Trying alternative pattern (unescaped)...")
        codigo_matches = re.findall(r'"codigo":\[0,"([^"]+)"\]', html_content)
        nombres_matches = re.findall(r'"nombres":\[0,"([^"]+)"\]', html_content)
        puntaje_matches = re.findall(r'"puntaje_final":\[0,([0-9.]+)\]', html_content)
        modalidad_matches = re.findall(r'"modalidad":\[0,"([^"]+)"\]', html_content)
        ingreso_matches = re.findall(r'"ingreso":\[0,(?:"([^"]+)"|null)\]', html_content)
        max_len = len(codigo_matches)
        print(f"Found (unescaped): {len(codigo_matches)} codigos, {len(nombres_matches)} nombres, {len(puntaje_matches)} puntajes")
    
    for i in range(max_len):
        if i < len(codigo_matches):
            # Extract ingreso (especialidad) - handle null case
            especialidad = ''
            if i < len(ingreso_matches):
                ingreso_val = ingreso_matches[i]
                if ingreso_val and ingreso_val != 'null':
                    especialidad = decode_html_entities(ingreso_val)
            
            results.append({
                'codigo': codigo_matches[i],
                'nombre_completo': decode_html_entities(nombres_matches[i] if i < len(nombres_matches) else ''),
                'modalidad': decode_html_entities(modalidad_matches[i] if i < len(modalidad_matches) else ''),
                'puntaje_final': puntaje_matches[i] if i < len(puntaje_matches) else '',
                'especialidad': especialidad
            })
    
    return results


def scrape_all_results() -> List[Dict[str, str]]:
    """Scrape all results from the page."""
    all_results = []
    
    print(f"Fetching data from {BASE_URL}...")
    html_content = get_page_content(BASE_URL)
    
    print("Extracting data from page...")
    results = extract_json_data(html_content)
    all_results.extend(results)
    
    print(f"\nTotal records scraped: {len(all_results)}")
    return all_results


def save_to_csv(results: List[Dict[str, str]], filename: str = 'resultados_uni.csv'):
    """Save results to CSV file."""
    if not results:
        print("No data to save to CSV")
        return
    
    fieldnames = ['codigo', 'nombre_completo', 'modalidad', 'puntaje_final', 'especialidad']
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"Data saved to {filename}")


def create_database(db_name: str = 'resultados_uni.db'):
    """Create SQLite database and table."""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    # Create table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resultados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL,
            nombre_completo TEXT,
            modalidad TEXT,
            puntaje_final REAL,
            especialidad TEXT,
            UNIQUE(codigo)
        )
    ''')
    
    # Create indexes for faster queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_especialidad ON resultados(especialidad)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_modalidad ON resultados(modalidad)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_puntaje ON resultados(puntaje_final)')
    
    conn.commit()
    return conn


def import_to_database(results: List[Dict[str, str]], conn: sqlite3.Connection):
    """Import results to SQLite database."""
    if not results:
        print("No data to import to database")
        return
    
    cursor = conn.cursor()
    
    # Clear existing data
    cursor.execute('DELETE FROM resultados')
    
    # Insert data
    for result in results:
        try:
            puntaje = float(result['puntaje_final'].replace(',', '.')) if result['puntaje_final'] else None
        except (ValueError, AttributeError):
            puntaje = None
        
        cursor.execute('''
            INSERT OR REPLACE INTO resultados 
            (codigo, nombre_completo, modalidad, puntaje_final, especialidad)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            result['codigo'],
            result['nombre_completo'],
            result['modalidad'],
            puntaje,
            result['especialidad']
        ))
    
    conn.commit()
    print(f"Imported {len(results)} records to database")


def run_analytics(conn: sqlite3.Connection):
    """Run analytics queries on the database."""
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("ANALYTICS RESULTS")
    print("="*60)
    
    # Total records
    cursor.execute('SELECT COUNT(*) FROM resultados')
    total = cursor.fetchone()[0]
    print(f"\nTotal de registros: {total}")
    
    # Number of ingresantes (assuming puntaje_final > 0 means admission)
    cursor.execute('SELECT COUNT(*) FROM resultados WHERE puntaje_final IS NOT NULL AND puntaje_final > 0')
    ingresantes = cursor.fetchone()[0]
    print(f"Total de ingresantes: {ingresantes}")
    
    # Statistics by especialidad
    print("\n" + "-"*60)
    print("ESTADÍSTICAS POR ESPECIALIDAD")
    print("-"*60)
    
    cursor.execute('''
        SELECT 
            especialidad,
            COUNT(*) as total_postulantes,
            COUNT(CASE WHEN puntaje_final IS NOT NULL AND puntaje_final > 0 THEN 1 END) as ingresantes,
            MAX(puntaje_final) as puntaje_maximo,
            MIN(puntaje_final) as puntaje_minimo,
            AVG(puntaje_final) as puntaje_promedio
        FROM resultados
        WHERE especialidad IS NOT NULL AND especialidad != ''
        GROUP BY especialidad
        ORDER BY ingresantes DESC
    ''')
    
    print(f"\n{'Especialidad':<40} {'Postulantes':<12} {'Ingresantes':<12} {'Max':<8} {'Min':<8} {'Promedio':<10}")
    print("-"*90)
    
    for row in cursor.fetchall():
        especialidad, total, ingresantes, max_p, min_p, avg_p = row
        especialidad = (especialidad[:37] + '...') if len(especialidad) > 40 else especialidad
        max_p = f"{max_p:.2f}" if max_p else "N/A"
        min_p = f"{min_p:.2f}" if min_p else "N/A"
        avg_p = f"{avg_p:.2f}" if avg_p else "N/A"
        print(f"{especialidad:<40} {total:<12} {ingresantes:<12} {max_p:<8} {min_p:<8} {avg_p:<10}")
    
    # Statistics by modalidad
    print("\n" + "-"*60)
    print("ESTADÍSTICAS POR MODALIDAD")
    print("-"*60)
    
    cursor.execute('''
        SELECT 
            modalidad,
            COUNT(*) as total,
            COUNT(CASE WHEN puntaje_final IS NOT NULL AND puntaje_final > 0 THEN 1 END) as ingresantes,
            MAX(puntaje_final) as puntaje_maximo,
            MIN(puntaje_final) as puntaje_minimo,
            AVG(puntaje_final) as puntaje_promedio
        FROM resultados
        WHERE modalidad IS NOT NULL AND modalidad != ''
        GROUP BY modalidad
        ORDER BY ingresantes DESC
    ''')
    
    print(f"\n{'Modalidad':<30} {'Total':<12} {'Ingresantes':<12} {'Max':<8} {'Min':<8} {'Promedio':<10}")
    print("-"*80)
    
    for row in cursor.fetchall():
        modalidad, total, ingresantes, max_p, min_p, avg_p = row
        modalidad = (modalidad[:27] + '...') if len(modalidad) > 30 else modalidad
        max_p = f"{max_p:.2f}" if max_p else "N/A"
        min_p = f"{min_p:.2f}" if min_p else "N/A"
        avg_p = f"{avg_p:.2f}" if avg_p else "N/A"
        print(f"{modalidad:<30} {total:<12} {ingresantes:<12} {max_p:<8} {min_p:<8} {avg_p:<10}")
    
    # Top 10 scores
    print("\n" + "-"*60)
    print("TOP 10 PUNTAJES MÁS ALTOS")
    print("-"*60)
    
    cursor.execute('''
        SELECT codigo, nombre_completo, especialidad, modalidad, puntaje_final
        FROM resultados
        WHERE puntaje_final IS NOT NULL
        ORDER BY puntaje_final DESC
        LIMIT 10
    ''')
    
    print(f"\n{'Código':<10} {'Nombre':<30} {'Especialidad':<25} {'Puntaje':<10}")
    print("-"*75)
    
    for row in cursor.fetchall():
        codigo, nombre, especialidad, modalidad, puntaje = row
        nombre = (nombre[:27] + '...') if nombre and len(nombre) > 30 else (nombre or 'N/A')
        especialidad = (especialidad[:22] + '...') if especialidad and len(especialidad) > 25 else (especialidad or 'N/A')
        print(f"{codigo:<10} {nombre:<30} {especialidad:<25} {puntaje:<10.2f}")


def main():
    """Main function."""
    print("UNI CEPRE Results Scraper")
    print("="*60)
    
    # Scrape data
    results = scrape_all_results()
    
    if not results:
        print("\nNo data found. The website structure might have changed.")
        print("Please check the website manually and update the scraper if needed.")
        return
    
    # Save to CSV
    save_to_csv(results)
    
    # Create and populate database
    conn = create_database()
    import_to_database(results, conn)
    
    # Run analytics
    run_analytics(conn)
    
    # Close connection
    conn.close()
    
    print("\n" + "="*60)
    print("Process completed successfully!")
    print("="*60)
    print(f"\nFiles created:")
    print(f"  - resultados_uni.csv")
    print(f"  - resultados_uni.db")


if __name__ == '__main__':
    main()
