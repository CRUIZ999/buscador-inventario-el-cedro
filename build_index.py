import pandas as pd
import sqlite3
import os
import datetime

# Lee el archivo Excel descargado por Render
EXCEL_PATH = "clasificacionanual1025.xlsx" # Asegúrate que el nombre sea correcto
# Nombre de la base de datos que se creará
DB_PATH = "inventario_el_cedro.db"

# --- MAPA EXACTO DE SUCURSALES ---
SUCURSAL_MAP = {
    'H ILUSTRES': 'HI',
    'EXPRESS': 'EX',
    'GENERAL': 'MT',
    'SAN AGUST': 'SA',
    'ADELITAS': 'ADE',
    # Añade más si es necesario (mayúsculas/minúsculas pueden importar)
}
# Lista de nombres cortos para asegurar el orden y filtrar
SUCURSALES_CORTAS = ['HI', 'EX', 'MT', 'SA', 'ADE']

def normalize_columns_to_text(cols):
    out = []
    for c in cols:
        val = str(c).strip() if pd.notna(c) else ""
        # Corregir posible error de pandas leyendo fechas como números flotantes
        if val.endswith(".0"):
            try:
                # Intentar convertir a entero si parece un número flotante terminado en .0
                val = str(int(float(val)))
            except ValueError:
                pass # Dejar como está si no se puede convertir
        out.append(val)
    return out

def detect_columns(df, needed_cols):
    """
    Detecta columnas necesarias (ej: ['Codigo', 'Descripcion', 'Lugar', 'Existencia'])
    """
    lower = [c.lower() for c in df.columns]
    # Mapeos flexibles conocidos
    col_map_options = {
        "Codigo": ["cve_prod", "codigo", "clave", "articulo", "sku"],
        "Descripcion": ["desc_prod", "descripcion", "producto", "nombre", "desc"],
        "Lugar": ["lugar", "sucursal", "tienda"], # Columna C en tu Excel
        "Existencia": ["inv", "existencia", "exist", "stock"], # Columna K en tu Excel
        "Clasificacion": ["clasificacion", "clasificación", "clase"] # Columna de las hojas Class
    }

    detected_map = {}
    missing = []

    for col_std in needed_cols:
        found_col = None
        if col_std in col_map_options:
            options = col_map_options[col_std]
            # Busca columnas cuyos nombres (en minúsculas) CONTENGAN alguna de las opciones
            found_col = next((df.columns[i] for i, c in enumerate(lower) if any(o in c for o in options)), None)

        if found_col:
            detected_map[col_std] = found_col
        else:
            # Si no se encuentra, añadir a la lista de faltantes
            missing.append(col_std)

    return detected_map, missing

def main():
    print("=" * 60)
    print(" BUSCADOR DE INVENTARIO – FERRETERÍA EL CEDRO (v3.1 - Mapeo Suc Exacto)")
    print("=" * 60)

    if not os.path.exists(EXCEL_PATH):
        print(f"❌ No se encontró el archivo Excel en: {EXCEL_PATH}")
        return

    print("\n[1/4] Leyendo hoja de Inventario (Inv)...")

    try:
        # --- Leer Hoja de Inventario ('Inv') ---
        # Asume header en fila 9 (índice 8)
        df_inv = pd.read_excel(EXCEL_PATH, sheet_name='Inv', header=8, engine='openpyxl')
        df_inv = df_inv.dropna(how='all').reset_index(drop=True) # Eliminar filas vacías
        df_inv.columns = normalize_columns_to_text(df_inv.columns) # Limpiar nombres de columnas

        inv_needed = ['Codigo', 'Descripcion', 'Lugar', 'Existencia']
        inv_map, inv_missing = detect_columns(df_inv, inv_needed)

        if inv_missing:
            print(f"❌ En la hoja 'Inv' faltan columnas clave: {inv_missing}")
            print("   Columnas detectadas en 'Inv':", list(df_inv.columns))
            return

        # Seleccionar y renombrar columnas de inventario
        df_inv = df_inv[list(inv_map.values())].rename(columns={v: k for k, v in inv_map.items()})

        # Limpiar datos básicos y convertir existencia
        df_inv['Codigo'] = df_inv['Codigo'].astype(str).str.strip()
        df_inv['Descripcion'] = df_inv['Descripcion'].astype(str).str.strip()
        df_inv['Lugar'] = df_inv['Lugar'].astype(str).str.strip()
        # Convertir Existencia a número, manejar errores poniendo 0
        df_inv['Existencia'] = pd.to_numeric(df_inv['Existencia'], errors='coerce').fillna(0)

        # Filtrar filas sin código o sin lugar (importantes para unir)
        df_inv = df_inv[(df_inv['Codigo'] != '') & (df_inv['Lugar'] != '')]
        print(f"✅ Hoja 'Inv' leída y limpiada: {len(df_inv)} registros.")

    except Exception as e:
        print(f"❌ Error crítico leyendo la hoja 'Inv': {e}")
        return

    print("\n[2/4] Leyendo hojas de Clasificación (Class(XX))...")

    clasif_frames = []
    column_mapping_ok = True

    try:
        xls = pd.ExcelFile(EXCEL_PATH, engine='openpyxl')
        hojas_class = [h for h in xls.sheet_names if h.lower().startswith("class")]
        print(f"Hojas de clasificación detectadas: {', '.join(hojas_class)}")

        for hoja in hojas_class:
            print(f" - Leyendo hoja: {hoja} ...")
            try:
                # Asume header en fila 9 (índice 8)
                df_class = pd.read_excel(EXCEL_PATH, sheet_name=hoja, header=8, engine='openpyxl')
                df_class = df_class.dropna(how='all').reset_index(drop=True)
                df_class.columns = normalize_columns_to_text(df_class.columns)

                # Para clasificación, necesitamos Código, Lugar y Clasificación
                class_needed = ['Codigo', 'Lugar', 'Clasificacion']
                class_map, class_missing = detect_columns(df_class, class_needed)

                if class_missing:
                    print(f"⚠️  En la hoja {hoja} faltan columnas para clasificación: {class_missing}")
                    print("   Columnas detectadas:", list(df_class.columns))
                    column_mapping_ok = False
                    continue # Saltar esta hoja

                # Seleccionar y renombrar
                tmp = df_class[list(class_map.values())].rename(columns={v: k for k, v in class_map.items()})

                # Limpiar datos
                tmp['Codigo'] = tmp['Codigo'].astype(str).str.strip()
                tmp['Lugar'] = tmp['Lugar'].astype(str).str.strip()
                tmp['Clasificacion'] = tmp['Clasificacion'].astype(str).fillna("").str.strip()
                # Filtrar filas sin código o sin lugar
                tmp = tmp[(tmp['Codigo'] != '') & (tmp['Lugar'] != '')]

                # Añadir columna con el nombre corto derivado del nombre de la hoja (para verificación)
                suc_from_sheet = hoja.replace("Class", "").replace("(", "").replace(")", "").strip()
                tmp['HojaOrigen'] = suc_from_sheet # Solo para referencia interna

                clasif_frames.append(tmp)
            except Exception as e:
                print(f"❌ Error procesando la hoja {hoja}: {e}")

    except Exception as e:
        print(f"❌ Error al intentar abrir o leer las hojas de clasificación: {e}")
        # Continuar si es posible, aunque la clasificación falle

    if not column_mapping_ok:
         print("⚠️  Faltaron columnas en algunas hojas de clasificación. Revisa los mensajes.")
    if not clasif_frames:
        print("⚠️ No se pudo leer datos de ninguna hoja de clasificación. Todos los productos quedarán sin clasificación asignada.")
        df_clasif_all = pd.DataFrame(columns=['Codigo', 'Lugar', 'Clasificacion']) # Crear DF vacío
    else:
        df_clasif_all = pd.concat(clasif_frames, ignore_index=True)
        # Quitar duplicados por si un producto/lugar aparece en varias hojas Class
        df_clasif_all = df_clasif_all.drop_duplicates(subset=['Codigo', 'Lugar'])
        print(f"✅ Hojas de clasificación leídas y combinadas: {len(df_clasif_all)} registros únicos.")

    print("\n[3/4] Uniendo Inventario y Clasificación, mapeando sucursales y agrupando...")

    # --- Unir Inv con Clasificación usando Codigo y Lugar ---
    # Left join para mantener todos los productos de Inv
    data_merged = pd.merge(df_inv, df_clasif_all[['Codigo', 'Lugar', 'Clasificacion']],
                           on=['Codigo', 'Lugar'], how='left')

    # Limpiar y asignar clasificación por defecto si falta
    data_merged['Clasificacion'] = data_merged['Clasificacion'].fillna("").astype(str).str.strip()
    data_merged['Clasificacion'] = data_merged['Clasificacion'].replace('', 'S/M') # Asignar S/M si está vacío

    # Mapear Lugar a Sucursal corta usando el diccionario SUCURSAL_MAP
    # Poner 'DESCONOCIDA' si el nombre largo no está en el mapa
    data_merged['Sucursal'] = data_merged['Lugar'].map(SUCURSAL_MAP).fillna('DESCONOCIDA')

    # Filtrar solo las sucursales conocidas que queremos (HI, EX, etc.)
    data_final_sucursales = data_merged[data_merged['Sucursal'].isin(SUCURSALES_CORTAS)].copy()

    # Agrupar por Codigo y Sucursal (corta), SUMAR Existencia
    # Tomar la primera Descripcion/Clasificacion encontrada (ya unidas)
    grouped_data = data_final_sucursales.groupby(['Codigo', 'Sucursal']).agg(
        Descripcion=('Descripcion', 'first'),
        Existencia=('Existencia', 'sum'),
        Clasificacion=('Clasificacion', 'first')
    ).reset_index()

    print(f"✅ Registros agrupados por sucursal: {len(grouped_data)}")

    # Calcular fila 'Global' sumando existencias por Codigo (de los datos ya agrupados por sucursal corta)
    global_stock = grouped_data.groupby('Codigo').agg(
         Descripcion=('Descripcion', 'first'),
         Existencia=('Existencia', 'sum'),
         # Clasificación Global: tomamos la primera encontrada (podría mejorarse si es necesario)
         Clasificacion=('Clasificacion', 'first')
    ).reset_index()
    global_stock['Sucursal'] = 'Global'

    # Unir datos agrupados por sucursal con los datos globales
    final_data = pd.concat([grouped_data, global_stock], ignore_index=True)

    # Convertir todas las columnas finales a texto para la DB
    for c in ["Codigo", "Descripcion", "Existencia", "Clasificacion", "Sucursal"]:
         # Asegurarse de que Existencia (que fue sumada) sea string sin decimales '.0'
         if c == 'Existencia':
             final_data[c] = final_data[c].astype(float).astype(int).astype(str)
         else:
             final_data[c] = final_data[c].astype(str).fillna("").str.strip()

    print(f"✅ Total de registros finales para DB (sucursales + global): {len(final_data)}")


    print("\n[4/4] Construyendo base de datos SQLite...")
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

    # ---- Tabla FTS5 (Solo Codigo y Descripcion únicos) ----
    try:
        cur.execute("DROP TABLE IF EXISTS inventario;")
        cur.execute("CREATE VIRTUAL TABLE inventario USING fts5(Codigo, Descripcion, content='');")
        unique_products = final_data[['Codigo', 'Descripcion']].drop_duplicates().values.tolist()
        cur.executemany("INSERT INTO inventario (Codigo, Descripcion) VALUES (?, ?);", unique_products)
    except Exception as e:
        print(f"⚠️ No se pudo crear/llenar la tabla FTS5: {e}")

    conn.commit()
    conn.close()

    print("✅ Base de datos creada correctamente.")

if __name__ == "__main__":
    main()