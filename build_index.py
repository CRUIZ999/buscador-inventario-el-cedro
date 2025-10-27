import pandas as pd
import sqlite3
import os
import datetime
import re # Para limpieza extra

# --- CONFIGURACIÓN ---
# Asegúrate que el nombre del archivo Excel sea EXACTO
EXCEL_PATH = "clasificacionanual1025.xlsx" 
DB_PATH = "inventario.db"

# Nombres cortos de las hojas que SÍ queremos leer
SUCURSALES_CORTAS = ['HI', 'EX', 'MT', 'SA', 'ADE']

# Columnas esperadas por ÍNDICE (0-based): B=1, D=3, E=4, FI=189
# ¡¡¡IMPORTANTE!!! AJUSTA EL ÍNDICE 189 SI 'FI' NO ES LA COLUMNA 190
COL_INDICES = {
    'Codigo': 1,        # Col B
    'Descripcion': 3,   # Col D
    'Existencia': 4,    # Col E
    'Clasificacion': 189 # Col FI (índice 189 si es la columna 190)
}
# Nombres estándar que usaremos en la base de datos
COL_NAMES = ['Codigo', 'Descripcion', 'Existencia', 'Clasificacion']
# --- FIN CONFIGURACIÓN ---


def clean_text(value):
    """Convierte a string, quita espacios y maneja None."""
    return str(value).strip() if pd.notna(value) else ""

def clean_existence(value):
    """Limpia la existencia: quita caracteres no numéricos (excepto '.') y convierte a float."""
    if pd.isna(value):
        return 0.0
    
    # Convertir a string, quitar espacios
    text_value = str(value).strip()
    
    # Quitar cualquier cosa que NO sea dígito, punto decimal o signo menos al inicio
    cleaned_text = re.sub(r"[^0-9.-]", "", text_value)
    
    # Manejar caso de solo '-' o '.'
    if cleaned_text in ['-', '.', '-.']:
         return 0.0
    try:
        # Intentar convertir a float
        return float(cleaned_text)
    except ValueError:
        # Si falla la conversión después de limpiar, devolver 0
        print(f"WARN: No se pudo convertir existencia '{value}' a número. Usando 0.")
        return 0.0

def main():
    print("=" * 60)
    print(" BUSCADOR DE INVENTARIO – FERRETERÍA EL CEDRO (v7 - Lectura Directa B,D,E,FI)")
    print("=" * 60)

    # --- [1/3] LEYENDO ARCHIVO EXCEL ---
    print(f"[1/3] Leyendo archivo '{EXCEL_PATH}'...")
    if not os.path.exists(EXCEL_PATH):
        print(f"❌ ERROR: ¡No se encuentra el archivo '{EXCEL_PATH}'!")
        print("   Asegúrate de que el archivo esté en el repositorio y tenga el nombre correcto.")
        return

    all_sucursal_data = []
    found_sheets = []

    try:
        xls = pd.ExcelFile(EXCEL_PATH, engine='openpyxl')
        
        # Leer solo las columnas que necesitamos por su índice
        column_indices_to_read = list(COL_INDICES.values())

        for hoja in xls.sheet_names:
            # Identificar si la hoja es una sucursal válida
            suc_code = next((s for s in SUCURSALES_CORTAS if s in hoja.upper()), None)

            if suc_code:
                found_sheets.append(hoja)
                print(f" - Leyendo hoja: {hoja} (Sucursal: {suc_code}) ...")
                try:
                    # --- LECTURA EFICIENTE ---
                    # Leer desde la fila 10 (skiprows=9), sin header automático
                    # usecols para leer solo las columnas B, D, E, FI por su índice
                    df = pd.read_excel(EXCEL_PATH, 
                                       sheet_name=hoja, 
                                       header=None, 
                                       skiprows=9,
                                       usecols=column_indices_to_read,
                                       engine='openpyxl')

                    # Asignar nombres estándar a las columnas leídas
                    df.columns = COL_NAMES

                    # --- LIMPIEZA DE DATOS ---
                    # Limpiar datos usando funciones específicas
                    df['Codigo'] = df['Codigo'].apply(clean_text)
                    df['Descripcion'] = df['Descripcion'].apply(clean_text)
                    df['Clasificacion'] = df['Clasificacion'].apply(clean_text).replace('', 'S/M')
                    
                    # Limpiar y convertir existencia a NÚMERO (float)
                    df['Existencia'] = df['Existencia'].apply(clean_existence)

                    # Filtrar filas sin código DESPUÉS de limpiar
                    original_rows = len(df)
                    df = df[df['Codigo'] != '']
                    if len(df) < original_rows:
                        print(f"   INFO: Se descartaron {original_rows - len(df)} filas sin código.")
                    
                    if df.empty:
                        print(f"   INFO: No se encontraron datos válidos en la hoja {hoja}.")
                        continue

                    # Añadir la columna Sucursal
                    df['Sucursal'] = suc_code
                    all_sucursal_data.append(df)
                    print(f"   INFO: Leídos {len(df)} registros válidos.")

                except Exception as e:
                    print(f"❌ Error procesando la hoja {hoja}: {e}")
                    import traceback
                    traceback.print_exc() # Imprimir detalle del error

    except Exception as e:
        print(f"❌ Error crítico al abrir o leer el archivo Excel: {e}")
        print("   (Si el error es 'no es un archivo zip', el archivo está corrupto o en formato .xls)")
        return

    if not all_sucursal_data:
        print("❌ No se pudieron leer datos válidos de ninguna hoja 'Class(XX)'.")
        return

    # Combinar datos de todas las sucursales leídas
    data_combined = pd.concat(all_sucursal_data, ignore_index=True)
    print(f"✅ Total registros leídos de {len(found_sheets)} hojas Class: {len(data_combined)}")

    # --- [2/3] AGRUPANDO DATOS ---
    print("\n[2/3] Agrupando datos y calculando Global...")

    # Agrupar por Codigo y Sucursal (elimina duplicados dentro de una hoja)
    grouped_data = data_combined.groupby(['Codigo', 'Sucursal']).agg(
        Descripcion=('Descripcion', 'first'),
        Existencia=('Existencia', 'sum'), # Sumar existencias numéricas
        Clasificacion=('Clasificacion', 'first')
    ).reset_index()

    # Calcular fila 'Global'
    global_stock = grouped_data.groupby('Codigo').agg(
         Descripcion=('Descripcion', 'first'),
         Existencia=('Existencia', 'sum'), # Suma numérica
         Clasificacion=('Clasificacion', 'first')
    ).reset_index()
    global_stock['Sucursal'] = 'Global'

    # Unir datos de sucursales con los datos globales
    final_data = pd.concat([grouped_data, global_stock], ignore_index=True)

    # Convertir columnas finales a texto para la DB
    for c in ["Codigo", "Descripcion", "Existencia", "Clasificacion", "Sucursal"]:
         if c == 'Existencia':
             # Convertir suma (posiblemente float) a entero y luego a string
             final_data[c] = final_data[c].round(0).astype(int).astype(str)
         else:
             final_data[c] = final_data[c].astype(str).fillna("").str.strip()

    print(f"✅ Total de registros finales para DB (sucursales + global): {len(final_data)}")
    print("   Ejemplo de datos finales:")
    print(final_data.head().to_string())

    # --- [3/3] CONSTRUYENDO DB SQLITE ---
    print(f"\n[3/3] Construyendo base de datos SQLite ('{DB_PATH}')...")
    
    # Eliminar DB antigua si existe
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print(f"   INFO: Base de datos '{DB_PATH}' existente eliminada.")
        except OSError as e:
            print(f"⚠️ WARN: No se pudo eliminar la base de datos existente: {e}")

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()

        # ---- Tabla NORMAL (Para búsquedas exactas) ----
        cur.execute("DROP TABLE IF EXISTS inventario_plain;") # Por si acaso
        cur.execute("CREATE TABLE inventario_plain (Codigo TEXT, Descripcion TEXT, Existencia TEXT, Clasificacion TEXT, Sucursal TEXT);")
        cur.executemany(
            "INSERT INTO inventario_plain (Codigo, Descripcion, Existencia, Clasificacion, Sucursal) VALUES (?, ?, ?, ?, ?);",
            final_data[["Codigo", "Descripcion", "Existencia", "Clasificacion", "Sucursal"]].values.tolist()
        )
        print("   INFO: Tabla 'inventario_plain' creada y poblada.")
        
        # Índices para búsquedas rápidas
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_desc ON inventario_plain(Descripcion);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_cod  ON inventario_plain(Codigo);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_suc  ON inventario_plain(Sucursal);")
        print("   INFO: Índices creados para 'inventario_plain'.")

        # ---- Tabla FTS5 (Para búsqueda de texto completo) ----
        cur.execute("DROP TABLE IF EXISTS inventario;") # Por si acaso
        cur.execute("CREATE VIRTUAL TABLE inventario USING fts5(Codigo, Descripcion, content='');")
        
        # Insertar solo los productos únicos (usamos los de 'Global')
        unique_products = final_data[final_data['Sucursal'] == 'Global'][['Codigo', 'Descripcion']].drop_duplicates().values.tolist()
        cur.executemany("INSERT INTO inventario (Codigo, Descripcion) VALUES (?, ?);", unique_products)
        print("   INFO: Tabla FTS 'inventario' creada y poblada.")

        conn.commit()
        print("\n✅ Base de datos creada y guardada correctamente.")

    except sqlite3.Error as e:
        print(f"❌ ERROR SQLite: {e}")
        conn.rollback() # Deshacer cambios si hubo error
    except Exception as e:
        print(f"❌ ERROR General al escribir en DB: {e}")
        conn.rollback()
    finally:
        conn.close() # Asegurar que la conexión se cierre

if __name__ == "__main__":
    main()