import pandas as pd
import sqlite3
import os
import datetime

# Lee el archivo Excel descargado por Render
EXCEL_PATH = "clasificacionanual1025.xlsx" # Asegúrate que el nombre sea correcto
# Nombre de la base de datos que se creará
DB_PATH = "inventario_el_cedro.db"

# Lista de nombres cortos para asegurar el orden y filtrar
SUCURSALES_CORTAS = ['HI', 'EX', 'MT', 'SA', 'ADE']

def normalize_columns_to_text(cols):
    """Limpia los nombres de las columnas."""
    out = []
    for c in cols:
        val = str(c).strip() if pd.notna(c) else ""
        # Corregir posible error de pandas leyendo fechas como números flotantes
        if val.endswith(".0"):
            try: val = str(int(float(val)))
            except ValueError: pass
        out.append(val)
    return out

def detect_columns(df):
    """
    Detecta las 4 columnas clave basado en nombres flexibles.
    """
    lower = [c.lower() for c in df.columns]
    # Mapeos flexibles conocidos
    col_map_options = {
        "Codigo": ["cve_prod", "codigo", "clave"],         # Col B
        "Descripcion": ["desc_prod", "descripcion"],      # Col D
        "Existencia": ["inv", "existencia", "stock"],     # Col E
        "Clasificacion": ["clasificacion", "clase", "fi"] # Col FI
    }

    detected_map = {}
    missing = []

    for std_name, options in col_map_options.items():
        # Busca columnas cuyos nombres (minúsculas) CONTENGAN alguna opción
        found_col = next((df.columns[i] for i, c in enumerate(lower) if any(o in c for o in options)), None)
        if found_col:
            detected_map[std_name] = found_col
        else:
            missing.append(std_name)

    return detected_map, missing

def main():
    print("=" * 60)
    print(" BUSCADOR DE INVENTARIO – FERRETERÍA EL CEDRO (v5 - Leer Solo Class XX)")
    print("=" * 60)

    if not os.path.exists(EXCEL_PATH):
        print(f"❌ No se encontró el archivo Excel en: {EXCEL_PATH}")
        return

    print("\n[1/3] Leyendo hojas de Sucursal (Class(XX))...")

    all_sucursal_data = []
    found_sheets = []

    try:
        xls = pd.ExcelFile(EXCEL_PATH, engine='openpyxl')
        hojas_class = [h for h in xls.sheet_names if h.lower().startswith("class")]
        print(f"Hojas de sucursal detectadas: {', '.join(hojas_class)}")

        if not hojas_class:
            print("❌ No se encontraron hojas que empiecen con 'Class'. Verifica nombres.")
            return

        for hoja in hojas_class:
            # Extraer código de sucursal del nombre de la hoja
            suc_code = hoja.replace("Class", "").replace("(", "").replace(")", "").strip().upper()
            if suc_code not in SUCURSALES_CORTAS:
                print(f"⚠️ Hoja '{hoja}' ignorada (código '{suc_code}' no reconocido).")
                continue

            found_sheets.append(hoja)
            print(f" - Leyendo hoja: {hoja} (Sucursal: {suc_code}) ...")
            try:
                # Asume encabezados en fila 9 (índice 8)
                df = pd.read_excel(EXCEL_PATH, sheet_name=hoja, header=8, engine='openpyxl')
                df = df.dropna(how='all').reset_index(drop=True)
                df.columns = normalize_columns_to_text(df.columns)

                detected_map, missing = detect_columns(df)

                if missing:
                    print(f"⚠️  En la hoja {hoja} faltan columnas: {missing}")
                    print("   Columnas detectadas:", list(df.columns))
                    print("   Saltando esta hoja.")
                    continue

                # Seleccionar y renombrar a nombres estándar
                df_suc = df[list(detected_map.values())].rename(columns={v: k for k, v in detected_map.items()})

                # Limpiar datos y convertir tipos
                df_suc['Codigo'] = df_suc['Codigo'].astype(str).str.strip()
                df_suc['Descripcion'] = df_suc['Descripcion'].astype(str).str.strip()
                df_suc['Clasificacion'] = df_suc['Clasificacion'].astype(str).fillna("").str.strip().replace('', 'S/M')
                df_suc['Existencia'] = pd.to_numeric(df_suc['Existencia'], errors='coerce').fillna(0)

                # Filtrar filas sin código
                df_suc = df_suc[df_suc['Codigo'] != '']

                # Añadir la columna Sucursal
                df_suc['Sucursal'] = suc_code

                all_sucursal_data.append(df_suc[['Codigo', 'Descripcion', 'Existencia', 'Clasificacion', 'Sucursal']])

            except Exception as e:
                print(f"❌ Error procesando la hoja {hoja}: {e}")

    except Exception as e:
        print(f"❌ Error crítico al abrir o leer el archivo Excel: {e}")
        return

    if not all_sucursal_data:
        print("❌ No se pudieron leer datos válidos de ninguna hoja 'Class(XX)'.")
        return

    # Combinar datos de todas las sucursales leídas
    data_combined = pd.concat(all_sucursal_data, ignore_index=True)
    print(f"✅ Total registros leídos de {len(found_sheets)} hojas Class: {len(data_combined)}")

    print("\n[2/3] Agrupando datos y calculando Global...")

    # Agrupar por Codigo y Sucursal (elimina duplicados dentro de una hoja si los hubiera)
    grouped_data = data_combined.groupby(['Codigo', 'Sucursal']).agg(
        Descripcion=('Descripcion', 'first'),
        Existencia=('Existencia', 'sum'), # Sumar si hay duplicados Codigo/Sucursal
        Clasificacion=('Clasificacion', 'first')
    ).reset_index()

    # Calcular fila 'Global'
    global_stock = grouped_data.groupby('Codigo').agg(
         Descripcion=('Descripcion', 'first'),
         Existencia=('Existencia', 'sum'), # Suma de todas las sucursales
         Clasificacion=('Clasificacion', 'first') # Tomamos la primera encontrada
    ).reset_index()
    global_stock['Sucursal'] = 'Global'

    # Unir datos de sucursales con los datos globales
    final_data = pd.concat([grouped_data, global_stock], ignore_index=True)

    # Convertir columnas finales a texto para la DB
    for c in ["Codigo", "Descripcion", "Existencia", "Clasificacion", "Sucursal"]:
         if c == 'Existencia':
             final_data[c] = final_data[c].astype(float).astype(int).astype(str) # Convertir suma a entero y luego a string
         else:
             final_data[c] = final_data[c].astype(str).fillna("").str.strip()

    print(f"✅ Total de registros finales para DB (sucursales + global): {len(final_data)}")

    print("\n[3/3] Construyendo base de datos SQLite...")
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # ---- Tabla NORMAL ----
    cur.execute("DROP TABLE IF EXISTS inventario_plain;")
    cur.execute("CREATE TABLE inventario_plain (Codigo TEXT, Descripcion TEXT, Existencia TEXT, Clasificacion TEXT, Sucursal TEXT);")
    cur.executemany(
        "INSERT INTO inventario_plain (Codigo, Descripcion, Existencia, Clasificacion, Sucursal) VALUES (?, ?, ?, ?, ?);",
        final_data[["Codigo", "Descripcion", "Existencia", "Clasificacion", "Sucursal"]].values.tolist()
    )
    # Índices
    cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_desc ON inventario_plain(Descripcion);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_cod  ON inventario_plain(Codigo);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_suc  ON inventario_plain(Sucursal);")

    # ---- Tabla FTS5 (Solo Codigo y Descripcion únicos de Global) ----
    try:
        cur.execute("DROP TABLE IF EXISTS inventario;")
        cur.execute("CREATE VIRTUAL TABLE inventario USING fts5(Codigo, Descripcion, content='');")
        unique_products = final_data[final_data['Sucursal'] == 'Global'][['Codigo', 'Descripcion']].drop_duplicates().values.tolist()
        cur.executemany("INSERT INTO inventario (Codigo, Descripcion) VALUES (?, ?);", unique_products)
    except Exception as e:
        print(f"⚠️ No se pudo crear/llenar la tabla FTS5: {e}")

    conn.commit()
    conn.close()

    print("✅ Base de datos creada correctamente.")

if __name__ == "__main__":
    main()