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
        if val.endswith(".0"): # Corregir fechas leídas como float
            try: val = str(int(float(val)))
            except ValueError: pass
        out.append(val)
    return out

def find_column_by_keywords(df_columns_lower, keywords):
    """Encuentra el nombre exacto de la columna que contenga alguna keyword."""
    for keyword in keywords:
        found = next((col for col in df_columns_lower if keyword in col), None)
        if found:
            # Necesitamos el nombre original, no el lower case
            original_index = df_columns_lower.index(found)
            return df.columns[original_index]
    return None

def main():
    print("=" * 60)
    print(" BUSCADOR DE INVENTARIO – FERRETERÍA EL CEDRO (v6 - Lectura Explícita)")
    print("=" * 60)

    if not os.path.exists(EXCEL_PATH):
        print(f"❌ No se encontró el archivo Excel en: {EXCEL_PATH}")
        return

    print("\n[1/3] Leyendo hojas de Sucursal (Class(XX))...")

    all_sucursal_data = []
    found_sheets = []

    # --- CORRECCIÓN: Nombres clave y sus posibles variaciones ---
    col_keywords = {
        "Codigo": ["cve_prod", "codigo", "clave"],         # Col B
        "Descripcion": ["desc_prod", "descripcion"],      # Col D
        "Existencia": ["inv", "existencia", "stock"],     # Col E
        "Clasificacion": ["clasificacion", "clase", "fi"] # Col FI
    }

    try:
        xls = pd.ExcelFile(EXCEL_PATH, engine='openpyxl')
        hojas_class = [h for h in xls.sheet_names if h.lower().startswith("class")]
        print(f"Hojas de sucursal detectadas: {', '.join(hojas_class)}")

        if not hojas_class:
            print("❌ No se encontraron hojas que empiecen con 'Class'. Verifica nombres.")
            return

        for hoja in hojas_class:
            suc_code = hoja.replace("Class", "").replace("(", "").replace(")", "").strip().upper()
            if suc_code not in SUCURSALES_CORTAS:
                print(f"⚠️ Hoja '{hoja}' ignorada (código '{suc_code}' no reconocido).")
                continue

            found_sheets.append(hoja)
            print(f" - Leyendo hoja: {hoja} (Sucursal: {suc_code}) ...")
            try:
                # Leer SIN encabezado automático, leeremos desde la fila 10 (índice 9)
                # IMPORTANTE: Ajusta header=None y skiprows=9 si tu primera fila de datos NO es la 10
                df = pd.read_excel(EXCEL_PATH, sheet_name=hoja, header=None, skiprows=9, engine='openpyxl')

                # --- CORRECCIÓN: Leer los encabezados de la fila 9 (ahora la primera fila leída, índice 0) ---
                # Asumimos que los nombres correctos están en la fila 9 del Excel original
                df_headers_raw = pd.read_excel(EXCEL_PATH, sheet_name=hoja, header=8, nrows=0, engine='openpyxl')
                df.columns = normalize_columns_to_text(df_headers_raw.columns) # Asignar nombres limpios

                df = df.dropna(how='all').reset_index(drop=True) # Quitar filas totalmente vacías
                df_cols_lower = [str(c).lower() for c in df.columns] # Nombres en minúscula para buscar

                # --- CORRECCIÓN: Detección explícita ---
                detected_cols = {}
                missing = []
                for std_name, keywords in col_keywords.items():
                    found_col_name = find_column_by_keywords(df_cols_lower, keywords)
                    if found_col_name:
                        detected_cols[std_name] = found_col_name
                    else:
                        missing.append(std_name)

                if missing:
                    print(f"⚠️  En la hoja {hoja} faltan columnas: {missing}")
                    print("   Columnas detectadas:", list(df.columns))
                    print("   Saltando esta hoja.")
                    continue

                # --- CORRECCIÓN: Seleccionar y renombrar explícitamente ---
                df_suc = df[[
                    detected_cols["Codigo"],
                    detected_cols["Descripcion"],
                    detected_cols["Existencia"],
                    detected_cols["Clasificacion"]
                ]].copy()
                df_suc.columns = ["Codigo", "Descripcion", "Existencia", "Clasificacion"] # Renombrar a estándar

                # Limpiar datos y convertir tipos
                df_suc['Codigo'] = df_suc['Codigo'].astype(str).str.strip()
                df_suc['Descripcion'] = df_suc['Descripcion'].astype(str).str.strip()
                df_suc['Clasificacion'] = df_suc['Clasificacion'].astype(str).fillna("").str.strip().replace('', 'S/M')
                # Forzar conversión a número ANTES de agrupar, manejar negativos
                df_suc['Existencia'] = pd.to_numeric(df_suc['Existencia'], errors='coerce').fillna(0)

                df_suc = df_suc[df_suc['Codigo'] != '']
                df_suc['Sucursal'] = suc_code

                all_sucursal_data.append(df_suc)

            except Exception as e:
                print(f"❌ Error procesando la hoja {hoja}: {e}")

    except Exception as e:
        print(f"❌ Error crítico al abrir o leer el archivo Excel: {e}")
        return

    if not all_sucursal_data:
        print("❌ No se pudieron leer datos válidos de ninguna hoja 'Class(XX)'.")
        return

    data_combined = pd.concat(all_sucursal_data, ignore_index=True)
    print(f"✅ Total registros leídos de {len(found_sheets)} hojas Class: {len(data_combined)}")

    print("\n[2/3] Agrupando datos y calculando Global...")

    # --- CORRECCIÓN: Asegurar que Existencia sea numérica ANTES de agrupar ---
    data_combined['Existencia'] = pd.to_numeric(data_combined['Existencia'], errors='coerce').fillna(0)

    grouped_data = data_combined.groupby(['Codigo', 'Sucursal']).agg(
        Descripcion=('Descripcion', 'first'),
        Existencia=('Existencia', 'sum'), # Ahora suma números
        Clasificacion=('Clasificacion', 'first')
    ).reset_index()

    global_stock = grouped_data.groupby('Codigo').agg(
         Descripcion=('Descripcion', 'first'),
         Existencia=('Existencia', 'sum'), # Suma números
         Clasificacion=('Clasificacion', 'first')
    ).reset_index()
    global_stock['Sucursal'] = 'Global'

    final_data = pd.concat([grouped_data, global_stock], ignore_index=True)

    # Convertir columnas finales a texto para la DB
    for c in ["Codigo", "Descripcion", "Existencia", "Clasificacion", "Sucursal"]:
         if c == 'Existencia':
             # Convertir suma (posiblemente float si hubo decimales) a entero y luego a string
             final_data[c] = final_data[c].astype(float).astype(int).astype(str)
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
    cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_desc ON inventario_plain(Descripcion);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_cod  ON inventario_plain(Codigo);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_suc  ON inventario_plain(Sucursal);")

    # ---- Tabla FTS5 ----
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