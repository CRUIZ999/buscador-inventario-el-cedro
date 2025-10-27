import pandas as pd
import sqlite3
import os
import datetime
import re # Para limpieza extra

# Lee el archivo Excel descargado por Render
EXCEL_PATH = "clasificacionanual1025.xlsx" # Asegúrate que el nombre sea correcto
# Nombre de la base de datos que se creará
DB_PATH = "inventario_el_cedro.db"

# Lista de nombres cortos para asegurar el orden y filtrar
SUCURSALES_CORTAS = ['HI', 'EX', 'MT', 'SA', 'ADE']

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

    if not os.path.exists(EXCEL_PATH):
        print(f"❌ No se encontró el archivo Excel en: {EXCEL_PATH}")
        return

    print("\n[1/3] Leyendo hojas de Sucursal (Class(XX))...")

    all_sucursal_data = []
    found_sheets = []
    # Columnas esperadas por ÍNDICE (0-based): B=1, D=3, E=4, FI=189 (asumiendo FI es la columna 190)
    # ¡¡¡IMPORTANTE!!! AJUSTA EL ÍNDICE DE CLASIFICACIÓN (ahora 189) SI 'FI' NO ES LA COLUMNA 190
    COL_INDICES = {
        'Codigo': 1,        # Col B
        'Descripcion': 3,   # Col D
        'Existencia': 4,    # Col E
        'Clasificacion': 189 # Col FI (índice 189 si es la columna 190)
    }
    # Nombres estándar que usaremos
    COL_NAMES = ['Codigo', 'Descripcion', 'Existencia', 'Clasificacion']

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
                # --- CORRECCIÓN CLAVE: Leer SIN header, saltar 9 filas, USAR ÍNDICES ---
                # Leer desde la fila 10 (skiprows=9), sin header automático
                # usecols para leer solo las columnas B, D, E, FI por su índice
                df = pd.read_excel(EXCEL_PATH, sheet_name=hoja, header=None, skiprows=9,
                                   usecols=[COL_INDICES['Codigo'], COL_INDICES['Descripcion'],
                                            COL_INDICES['Existencia'], COL_INDICES['Clasificacion']],
                                   engine='openpyxl')

                # Asignar nombres estándar a las columnas leídas
                df.columns = COL_NAMES

                df = df.dropna(how='all').reset_index(drop=True) # Quitar filas totalmente vacías

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

                print(f"   INFO: Leídos {len(df)} registros válidos.")
                all_sucursal_data.append(df) # Añadir DataFrame limpio

            except Exception as e:
                print(f"❌ Error procesando la hoja {hoja}: {e}")
                import traceback
                traceback.print_exc() # Imprimir detalle del error

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

    # Asegurarse de que Existencia es numérica antes de agrupar
    data_combined['Existencia'] = pd.to_numeric(data_combined['Existencia'], errors='coerce').fillna(0)

    # Agrupar por Codigo y Sucursal (elimina duplicados dentro de una hoja si los hubiera)
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
    # Imprimir algunas filas de ejemplo para verificar en logs
    print("   Ejemplo de datos finales:")
    print(final_data.head().to_string())


    print("\n[3/3] Construyendo base de datos SQLite...")
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print(f"   INFO: Base de datos '{DB_PATH}' existente eliminada.")
        except OSError as e:
            print(f"⚠️ WARN: No se pudo eliminar la base de datos existente: {e}")


    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        # ---- Tabla NORMAL ----
        cur.execute("DROP TABLE IF EXISTS inventario_plain;") # Por si acaso
        cur.execute("CREATE TABLE inventario_plain (Codigo TEXT, Descripcion TEXT, Existencia TEXT, Clasificacion TEXT, Sucursal TEXT);")
        cur.executemany(
            "INSERT INTO inventario_plain (Codigo, Descripcion, Existencia, Clasificacion, Sucursal) VALUES (?, ?, ?, ?, ?);",
            final_data[["Codigo", "Descripcion", "Existencia", "Clasificacion", "Sucursal"]].values.tolist()
        )
        print("   INFO: Tabla 'inventario_plain' creada y poblada.")
        # Índices
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_desc ON inventario_plain(Descripcion);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_cod  ON inventario_plain(Codigo);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_suc  ON inventario_plain(Sucursal);")
        print("   INFO: Índices creados para 'inventario_plain'.")

        # ---- Tabla FTS5 ----
        cur.execute("DROP TABLE IF EXISTS inventario;") # Por si acaso
        cur.execute("CREATE VIRTUAL TABLE inventario USING fts5(Codigo, Descripcion, content='');")
        unique_products = final_data[final_data['Sucursal'] == 'Global'][['Codigo', 'Descripcion']].drop_duplicates().values.tolist()
        cur.executemany("INSERT INTO inventario (Codigo, Descripcion) VALUES (?, ?);", unique_products)
        print("   INFO: Tabla FTS 'inventario' creada y poblada.")

        conn.commit()
        print("✅ Base de datos creada y guardada correctamente.")

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