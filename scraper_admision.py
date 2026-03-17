#!/usr/bin/env python3
"""
Script to scrape UNI Examen de Admisión results from all exam sub-pages.
Combines individual exam scores with final results per applicant.
"""

import csv
import html
import re
import sqlite3
import sys
import urllib.request
from typing import Dict, List


BASE_URL = "https://puntajes.admision.uni.edu.pe/admision"

EXAM_PAGES = {
    'aptitud_vocacional': f'{BASE_URL}/aptitud-vocacional/',
    'aptitud_academica': f'{BASE_URL}/aptitud-academica/',
    'matematica': f'{BASE_URL}/matematica/',
    'fisica_quimica': f'{BASE_URL}/fisica-quimica/',
    'traslado_externo': f'{BASE_URL}/traslado-externo/',
}

FINAL_RESULTS_URL = f'{BASE_URL}/resultados-finales/'


def get_page_content(url: str) -> str:
    """Fetch page content using urllib."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(req, timeout=60)
        return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""


def decode_html_entities(text: str) -> str:
    """Decode HTML entities to proper UTF-8 characters."""
    text = html.unescape(text)
    try:
        if 'Ã' in text or 'Ã©' in text:
            text = text.encode('latin-1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    return text


def extract_exam_scores(html_content: str) -> List[Dict]:
    """Extract exam scores from individual exam pages (codigo, nombres, puntaje)."""
    results = []

    codigos = re.findall(r'&quot;codigo&quot;:\[0,&quot;([^&]+)&quot;\]', html_content)
    nombres = re.findall(r'&quot;nombres&quot;:\[0,&quot;([^&]+)&quot;\]', html_content)
    # Puntaje can be a string like &quot;42.000&quot; or a bare number
    puntajes = re.findall(r'&quot;puntaje&quot;:\[0,(?:&quot;([^&]+)&quot;|([0-9.-]+))\]', html_content)

    for i in range(len(codigos)):
        puntaje = None
        if i < len(puntajes):
            val = puntajes[i][0] or puntajes[i][1]
            try:
                puntaje = float(val)
            except (ValueError, TypeError):
                pass
        results.append({
            'codigo': codigos[i],
            'nombres': decode_html_entities(nombres[i] if i < len(nombres) else ''),
            'puntaje': puntaje,
        })

    return results


def extract_final_results(html_content: str) -> List[Dict]:
    """Extract final admission results (codigo, nombres, puntaje_final, ingreso, modalidad, observacion)."""
    results = []

    codigos = re.findall(r'&quot;codigo&quot;:\[0,&quot;([^&]+)&quot;\]', html_content)
    nombres = re.findall(r'&quot;nombres&quot;:\[0,&quot;([^&]+)&quot;\]', html_content)
    puntajes = re.findall(r'&quot;puntaje_final&quot;:\[0,([0-9.-]+)\]', html_content)
    ingresos = re.findall(r'&quot;ingreso&quot;:\[0,(?:&quot;([^&]*)&quot;|null)\]', html_content)
    modalidades = re.findall(r'&quot;modalidad&quot;:\[0,&quot;([^&]+)&quot;\]', html_content)
    observaciones = re.findall(r'&quot;observacion&quot;:\[0,(?:&quot;([^&]*)&quot;|null)\]', html_content)

    for i in range(len(codigos)):
        ingreso = ''
        if i < len(ingresos) and ingresos[i]:
            ingreso = decode_html_entities(ingresos[i])

        observacion = ''
        if i < len(observaciones) and observaciones[i]:
            observacion = decode_html_entities(observaciones[i])

        results.append({
            'codigo': codigos[i],
            'nombre_completo': decode_html_entities(nombres[i] if i < len(nombres) else ''),
            'puntaje_final': float(puntajes[i]) if i < len(puntajes) else None,
            'especialidad_ingreso': ingreso,
            'modalidad': decode_html_entities(modalidades[i] if i < len(modalidades) else ''),
            'observacion': observacion,
        })

    return results


def scrape_all():
    """Scrape all exam pages and final results, merge by codigo."""

    # 1. Scrape individual exam scores
    exam_scores = {}  # codigo -> {exam_name: puntaje}

    for exam_name, url in EXAM_PAGES.items():
        print(f"Scraping {exam_name} from {url}...")
        content = get_page_content(url)
        if not content:
            print(f"  No content for {exam_name}, skipping.")
            continue

        scores = extract_exam_scores(content)
        print(f"  Found {len(scores)} records")

        for s in scores:
            codigo = s['codigo']
            if codigo not in exam_scores:
                exam_scores[codigo] = {'nombre_completo': s['nombres']}
            exam_scores[codigo][exam_name] = s['puntaje']

    # 2. Scrape final results
    print(f"\nScraping resultados finales from {FINAL_RESULTS_URL}...")
    content = get_page_content(FINAL_RESULTS_URL)
    final_results = extract_final_results(content)
    print(f"  Found {len(final_results)} records")

    # 3. Merge everything by codigo
    merged = []
    for fr in final_results:
        codigo = fr['codigo']
        scores = exam_scores.get(codigo, {})

        merged.append({
            'codigo': codigo,
            'nombre_completo': fr['nombre_completo'],
            'modalidad': fr['modalidad'],
            'puntaje_aptitud_vocacional': scores.get('aptitud_vocacional'),
            'puntaje_aptitud_academica': scores.get('aptitud_academica'),
            'puntaje_matematica': scores.get('matematica'),
            'puntaje_fisica_quimica': scores.get('fisica_quimica'),
            'puntaje_traslado_externo': scores.get('traslado_externo'),
            'puntaje_final': fr['puntaje_final'],
            'especialidad_ingreso': fr['especialidad_ingreso'],
            'observacion': fr['observacion'],
        })

    # Add students who appear in exams but NOT in final results
    final_codigos = {fr['codigo'] for fr in final_results}
    for codigo, scores in exam_scores.items():
        if codigo not in final_codigos:
            merged.append({
                'codigo': codigo,
                'nombre_completo': scores.get('nombre_completo', ''),
                'modalidad': '',
                'puntaje_aptitud_vocacional': scores.get('aptitud_vocacional'),
                'puntaje_aptitud_academica': scores.get('aptitud_academica'),
                'puntaje_matematica': scores.get('matematica'),
                'puntaje_fisica_quimica': scores.get('fisica_quimica'),
                'puntaje_traslado_externo': scores.get('traslado_externo'),
                'puntaje_final': None,
                'especialidad_ingreso': '',
                'observacion': '',
            })

    print(f"\nTotal merged records: {len(merged)}")
    return merged


FIELDNAMES = [
    'codigo', 'nombre_completo', 'modalidad',
    'puntaje_aptitud_vocacional', 'puntaje_aptitud_academica',
    'puntaje_matematica', 'puntaje_fisica_quimica', 'puntaje_traslado_externo',
    'puntaje_final', 'especialidad_ingreso', 'observacion',
]


def save_to_csv(results: List[Dict], filename: str = 'resultados_admision.csv'):
    """Save results to CSV file."""
    if not results:
        print("No data to save to CSV")
        return

    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(results)

    print(f"Data saved to {filename}")


def create_database(db_name: str = 'resultados_admision.db'):
    """Create SQLite database and tables."""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admision (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL,
            nombre_completo TEXT,
            modalidad TEXT,
            puntaje_aptitud_vocacional REAL,
            puntaje_aptitud_academica REAL,
            puntaje_matematica REAL,
            puntaje_fisica_quimica REAL,
            puntaje_traslado_externo REAL,
            puntaje_final REAL,
            especialidad_ingreso TEXT,
            observacion TEXT,
            UNIQUE(codigo)
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_adm_especialidad ON admision(especialidad_ingreso)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_adm_modalidad ON admision(modalidad)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_adm_puntaje_final ON admision(puntaje_final)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_adm_puntaje_mat ON admision(puntaje_matematica)')

    conn.commit()
    return conn


def import_to_database(results: List[Dict], conn: sqlite3.Connection):
    """Import results to SQLite database."""
    if not results:
        print("No data to import to database")
        return

    cursor = conn.cursor()
    cursor.execute('DELETE FROM admision')

    for r in results:
        cursor.execute('''
            INSERT OR REPLACE INTO admision
            (codigo, nombre_completo, modalidad,
             puntaje_aptitud_vocacional, puntaje_aptitud_academica,
             puntaje_matematica, puntaje_fisica_quimica, puntaje_traslado_externo,
             puntaje_final, especialidad_ingreso, observacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            r['codigo'], r['nombre_completo'], r['modalidad'],
            r['puntaje_aptitud_vocacional'], r['puntaje_aptitud_academica'],
            r['puntaje_matematica'], r['puntaje_fisica_quimica'], r['puntaje_traslado_externo'],
            r['puntaje_final'], r['especialidad_ingreso'], r['observacion'],
        ))

    conn.commit()
    print(f"Imported {len(results)} records to database")


def run_analytics(conn: sqlite3.Connection):
    """Run analytics queries on the database."""
    cursor = conn.cursor()

    print("\n" + "=" * 70)
    print("EXAMEN DE ADMISIÓN UNI - ANALYTICS")
    print("=" * 70)

    # General stats
    cursor.execute('SELECT COUNT(*) FROM admision')
    total = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM admision WHERE especialidad_ingreso IS NOT NULL AND especialidad_ingreso != ""')
    ingresantes = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(DISTINCT modalidad) FROM admision WHERE modalidad != ""')
    modalidades = cursor.fetchone()[0]

    print(f"\nTotal postulantes: {total}")
    print(f"Total ingresantes: {ingresantes}")
    print(f"Tasa de ingreso: {ingresantes/total*100:.1f}%" if total > 0 else "")
    print(f"Modalidades: {modalidades}")

    # Exam score averages
    print("\n" + "-" * 70)
    print("PROMEDIOS POR EXAMEN")
    print("-" * 70)

    for exam_col, label in [
        ('puntaje_aptitud_vocacional', 'Aptitud Vocacional'),
        ('puntaje_aptitud_academica', 'Aptitud Académica'),
        ('puntaje_matematica', 'Matemática'),
        ('puntaje_fisica_quimica', 'Física y Química'),
    ]:
        cursor.execute(f'''
            SELECT COUNT(*), AVG({exam_col}), MAX({exam_col}), MIN({exam_col})
            FROM admision WHERE {exam_col} IS NOT NULL
        ''')
        row = cursor.fetchone()
        if row and row[0] > 0:
            print(f"  {label:<25} Rindieron: {row[0]:<6} Promedio: {row[1]:>7.2f}  Max: {row[2]:>7.2f}  Min: {row[3]:>7.2f}")

    # Stats by especialidad
    print("\n" + "-" * 70)
    print("ESTADÍSTICAS POR ESPECIALIDAD (ingresantes)")
    print("-" * 70)

    cursor.execute('''
        SELECT
            especialidad_ingreso,
            COUNT(*) as ingresantes,
            MAX(puntaje_final) as max_p,
            MIN(puntaje_final) as min_p,
            AVG(puntaje_final) as avg_p
        FROM admision
        WHERE especialidad_ingreso IS NOT NULL AND especialidad_ingreso != ''
        GROUP BY especialidad_ingreso
        ORDER BY ingresantes DESC
    ''')

    print(f"\n{'Especialidad':<45} {'Ingresantes':<12} {'Max':<8} {'Min':<8} {'Promedio':<10}")
    print("-" * 85)

    for row in cursor.fetchall():
        esp, ing, max_p, min_p, avg_p = row
        esp = (esp[:42] + '...') if len(esp) > 45 else esp
        print(f"{esp:<45} {ing:<12} {max_p:<8.1f} {min_p:<8.1f} {avg_p:<10.1f}")

    # Stats by modalidad
    print("\n" + "-" * 70)
    print("ESTADÍSTICAS POR MODALIDAD")
    print("-" * 70)

    cursor.execute('''
        SELECT
            modalidad,
            COUNT(*) as total,
            COUNT(CASE WHEN especialidad_ingreso != '' THEN 1 END) as ingresantes,
            AVG(puntaje_final) as avg_p
        FROM admision
        WHERE modalidad IS NOT NULL AND modalidad != ''
        GROUP BY modalidad
        ORDER BY total DESC
    ''')

    print(f"\n{'Modalidad':<50} {'Postulantes':<12} {'Ingresantes':<12} {'Tasa %':<8}")
    print("-" * 85)

    for row in cursor.fetchall():
        mod, total, ing, avg_p = row
        mod = (mod[:47] + '...') if len(mod) > 50 else mod
        tasa = f"{ing/total*100:.1f}" if total > 0 else "0.0"
        print(f"{mod:<50} {total:<12} {ing:<12} {tasa:<8}")

    # Top 10 scores
    print("\n" + "-" * 70)
    print("TOP 10 PUNTAJES MÁS ALTOS")
    print("-" * 70)

    cursor.execute('''
        SELECT codigo, nombre_completo, especialidad_ingreso, puntaje_final,
               puntaje_matematica, puntaje_fisica_quimica, puntaje_aptitud_academica
        FROM admision
        WHERE puntaje_final IS NOT NULL
        ORDER BY puntaje_final DESC
        LIMIT 10
    ''')

    print(f"\n{'Código':<10} {'Nombre':<30} {'Especialidad':<25} {'Final':<8} {'Mat':<8} {'Fis/Qui':<8} {'Acad':<8}")
    print("-" * 100)

    for row in cursor.fetchall():
        codigo, nombre, esp, final, mat, fq, acad = row
        nombre = (nombre[:27] + '...') if nombre and len(nombre) > 30 else (nombre or '')
        esp = (esp[:22] + '...') if esp and len(esp) > 25 else (esp or '')
        mat_s = f"{mat:.1f}" if mat else "-"
        fq_s = f"{fq:.1f}" if fq else "-"
        acad_s = f"{acad:.1f}" if acad else "-"
        print(f"{codigo:<10} {nombre:<30} {esp:<25} {final:<8.1f} {mat_s:<8} {fq_s:<8} {acad_s:<8}")


def main():
    print("UNI Examen de Admisión - Scraper")
    print("=" * 70)

    results = scrape_all()

    if not results:
        print("\nNo data found. The website structure might have changed.")
        return

    save_to_csv(results)

    conn = create_database()
    import_to_database(results, conn)
    run_analytics(conn)
    conn.close()

    print("\n" + "=" * 70)
    print("Process completed!")
    print("=" * 70)
    print(f"\nFiles created:")
    print(f"  - resultados_admision.csv")
    print(f"  - resultados_admision.db")


if __name__ == '__main__':
    main()
