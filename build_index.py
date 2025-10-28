import pandas as pd
import sqlite3
import os
import datetime
import re
import glob # Para buscar los archivos CSV

# --- CONFIGURACIÓN ---
DB_PATH = "inventario.db"

# Los 5 archivos CSV que esperamos encontrar. 
# El nombre del archivo (sin .csv) será el código de la sucursal.
SUCURSALES_FILES = ['hi', 'ex', 'mt', 'sa', 'ade']

# Columnas esperadas por ÍNDICE (0-based):
# B=1, D=3, E=4, AQ=41, FI=189
COL_INDICES = {
    'Codigo': 1,        # Col B
    'Descripcion': 3,   # Col D
    'Existencia': 4,    # Col E
    'DescProd2': 41,    # Col AQ (NUEVA)
    'Clasificacion': 189 # Col FI
}
# Nombres estándar que usaremos
COL_NAMES = ['Codigo', 'Descripcion', 'Existencia', 'DescProd2', 'Clasificacion']
# --- FIN CONFIGURACIÓN ---


def clean_text(value):
    """Convierte a string, quita espacios y maneja None."""
    return str(value).strip() if pd.notna(value) else ""

def clean_existence(value):
    """Limpia la existencia: quita caracteres no numéricos (excepto '.') y convierte a float."""
    if pd.isna(value):
        return 0.0
    text_value = str(value).strip()
    cleaned_text = re.sub(r"[^0-9.-]", "", text_value)
    if cleaned_text in ['-', '.', '-.']:
         return 0.0
    try:
        return float(cleaned_text)
    except ValueError:
        print(f"WARN: No se pudo convertir existencia '{value}' a número. Usando 0.")
        return 0.0

def main():
    print("=" * 60)
    print(" BUSCADOR DE INVENTARIO – FERRETERÍA EL CEDRO (v9 - Lector CSV Múltiple + AQ)")
    print("=" * 60)

    # --- [1/3] LEYENDO ARCHIVOS CSV ---
    print(f"[1/3] Buscando archivos {', '.join(SUCURSALES_FILES)}...")

    all_sucursal_data = []
    found_files_count = 0

    # Leer solo las columnas que necesitamos por su índice
    column_indices_to_read = list(COL_INDICES.values())

    for suc_code in SUCURSALES_FILES:
        file_path = f"{suc_code}.csv"
        if not os.path.exists(file_path):
            print(f"⚠️  WARN: No se encontró el archivo '{file_path}'. Saltando sucursal.")
            continue

        print(f" - Leyendo archivo: {file_path} (Sucursal: {suc_code.upper()}) ...")
        found_files_count += 1
        
        try:
            # --- LECTURA EFICIENTE DE CSV ---
            df = pd.read_csv(
                file_path,
                header=None, 
                skiprows=9,
                usecols=column_indices_to_read,
                encoding='latin1', # Probar 'latin1' o 'ISO-8859-1' si 'utf-8' falla
                on_bad_lines='skip',
                dtype=str # Leer todo como texto primero para evitar errores
            )

            # Asignar nombres estándar a las columnas leídas
            df.columns = COL_NAMES

            # --- LIMPIEZA DE DATOS ---
            df['Codigo'] = df['Codigo'].apply(clean_text)
            df['Descripcion'] = df['Descripcion'].apply(clean_text)
            df['DescProd2'] = df['DescProd2'].apply(clean_text) # NUEVA
            df['Clasificacion'] = df['Clasificacion'].apply(clean_text).replace('', 'S/M')
            df['Existencia'] = df['Existencia'].apply(clean_existence)

            original_rows = len(df)
            df = df[df['Codigo'] != '']
            if len(df) < original_rows:
                print(f"   INFO: Se descartaron {original_rows - len(df)} filas sin código.")
            
            if df.empty:
                print(f"   INFO: No se encontraron datos válidos en el archivo {file_path}.")
                continue

            df['Sucursal'] = suc_code.upper()
            all_sucursal_data.append(df)
            print(f"   INFO: Leídos {len(df)} registros válidos.")

        except Exception as e:
            print(f"❌ Error procesando el archivo {file_path}: {e}")
            import traceback
            traceback.print_exc()

    if not all_sucursal_data:
        print("❌ No se pudieron leer datos válidos de ningún archivo CSV.")
        return

    print(f"✅ Total archivos leídos: {found_files_count}")
    data_combined = pd.concat(all_sucursal_data, ignore_index=True)
    print(f"✅ Total registros leídos de todos los CSV: {len(data_combined)}")

    # --- [2/3] AGRUPANDO DATOS ---
    print("\n[2/3] Agrupando datos y calculando Global...")

    grouped_data = data_combined.groupby(['Codigo', 'Sucursal']).agg(
        Descripcion=('Descripcion', 'first'),
        DescProd2=('DescProd2', 'first'), # NUEVA
        Existencia=('Existencia', 'sum'),
        Clasificacion=('Clasificacion', 'first')
    ).reset_index()

    global_stock = grouped_data.groupby('Codigo').agg(
         Descripcion=('Descripcion', 'first'),
         DescProd2=('DescProd2', 'first'), # NUEVA
         Existencia=('Existencia', 'sum'),
         Clasificacion=('Clasificacion', 'first')
    ).reset_index()
    global_stock['Sucursal'] = 'Global'

    final_data = pd.concat([grouped_data, global_stock], ignore_index=True)

    # Convertir columnas finales a texto para la DB
    for c in ["Codigo", "Descripcion", "DescProd2", "Existencia", "Clasificacion", "Sucursal"]:
         if c == 'Existencia':
             final_data[c] = final_data[c].round(0).astype(int).astype(str)
         else:
             final_data[c] = final_data[c].astype(str).fillna("").str.strip()

    print(f"✅ Total de registros finales para DB: {len(final_data)}")
    print("   Ejemplo de datos finales:")
    print(final_data.head().to_string())

    # --- [3/3] CONSTRUYENDO DB SQLITE ---
    print(f"\n[3/3] Construyendo base de datos SQLite ('{DB_PATH}')...")
    
    # Cambiamos el nombre de la DB a inventario.db
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print(f"   INFO: Base de datos '{DB_PATH}' existente eliminada.")
        except OSError as e:
            print(f"⚠️ WARN: No se pudo eliminar la base de datos existente: {e}")

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()

        # ---- Tabla NORMAL (Para detalles) ----
        cur.execute("DROP TABLE IF EXISTS inventario_plain;")
        # NUEVA: Añadida DescProd2
        cur.execute("CREATE TABLE inventario_plain (Codigo TEXT, Descripcion TEXT, DescProd2 TEXT, Existencia TEXT, Clasificacion TEXT, Sucursal TEXT);")
        cur.executemany(
            # NUEVA: Añadida DescProd2
            "INSERT INTO inventario_plain (Codigo, Descripcion, DescProd2, Existencia, Clasificacion, Sucursal) VALUES (?, ?, ?, ?, ?, ?);",
            final_data[["Codigo", "Descripcion", "DescProd2", "Existencia", "Clasificacion", "Sucursal"]].values.tolist()
        )
        print("   INFO: Tabla 'inventario_plain' creada y poblada.")
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_cod  ON inventario_plain(Codigo);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_suc  ON inventario_plain(Sucursal);")
        print("   INFO: Índices creados para 'inventario_plain'.")

        # ---- Tabla FTS5 (Para búsqueda rápida) ----
        cur.execute("DROP TABLE IF EXISTS inventario;")
        # NUEVA: Añadida DescProd2
        cur.execute("CREATE VIRTUAL TABLE inventario USING fts5(Codigo, Descripcion, DescProd2, content='');")
        
        # NUEVA: Añadida DescProd2
        unique_products = final_data[final_data['Sucursal'] == 'Global'][['Codigo', 'Descripcion', 'DescProd2']].drop_duplicates().values.tolist()
        cur.executemany("INSERT INTO inventario (Codigo, Descripcion, DescProd2) VALUES (?, ?, ?);", unique_products)
        print("   INFO: Tabla FTS 'inventario' creada y poblada.")

        conn.commit()
        print("\n✅ Base de datos creada y guardada correctamente.")

    except sqlite3.Error as e:
        print(f"❌ ERROR SQLite: {e}")
        conn.rollback()
    except Exception as e:
        print(f"❌ ERROR General al escribir en DB: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()