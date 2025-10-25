import pandas as pd
import sqlite3
import os
import datetime

# Lee el archivo Excel descargado por Render
EXCEL_PATH = "clasificacionanual102025.xlsx"
# Nombre de la base de datos que se creará
DB_PATH = "inventario_el_cedro.db"

def normalize_columns_to_text(cols):
    out = []
    for c in cols:
        if isinstance(c, datetime.datetime):
            out.append(c.strftime("%Y-%m-%d"))
        else:
            out.append(str(c).strip())
    return out

def detect_columns(df):
    """
    Mapea columnas del Excel a las 4 claves estándar:
    Codigo, Descripcion, Existencia, Clasificacion
    con detección flexible (cve_prod, desc_prod, Inv, Clasificacion, etc.)
    """
    lower = [c.lower() for c in df.columns]
    find = lambda *opts: next((df.columns[i] for i, c in enumerate(lower) if any(o in c for o in opts)), None)

    col_codigo = find("cve_prod", "codigo", "clave", "articulo", "sku")
    col_desc   = find("desc_prod", "descripcion", "producto", "nombre", "desc")
    col_inv    = find("inv", "existencia", "exist", "stock")
    col_clas   = find("clasificacion", "clasificación", "clase")

    missing = [n for n, v in {"Codigo": col_codigo, "Descripcion": col_desc, "Existencia": col_inv, "Clasificacion": col_clas}.items() if v is None]
    return (col_codigo, col_desc, col_inv, col_clas, missing)

def main():
    print("=" * 60)
    print(" BUSCADOR DE INVENTARIO – FERRETERÍA EL CEDRO")
    print("=" * 60)

    if not os.path.exists(EXCEL_PATH):
        print(f"❌ No se encontró el archivo Excel en: {EXCEL_PATH}")
        # Ya no usamos input(), salimos directamente si hay error
        return # Termina el script

    print("\n[1/2] Construyendo índice (SQLite + tablas normal + FTS5)...")

    try:
        xls = pd.ExcelFile(EXCEL_PATH)
        hojas = [h for h in xls.sheet_names if h.lower().startswith("class")]
        print(f"Hojas detectadas: {', '.join(hojas)}")
    except Exception as e:
        print(f"❌ Error al intentar abrir o leer las hojas del archivo Excel: {e}")
        print("   Asegúrate de que el archivo descargado sea un Excel válido.")
        return # Termina el script

    frames = []

    for hoja in hojas:
        print(f" - Leyendo hoja: {hoja} ...")
        try:
            # Asume que los encabezados están en la fila 9 (índice 8)
            df = pd.read_excel(EXCEL_PATH, sheet_name=hoja, header=8)
            df.columns = normalize_columns_to_text(df.columns)

            col_codigo, col_desc, col_inv, col_clas, missing = detect_columns(df)
            if missing:
                print(f"⚠️  En la hoja {hoja} no se detectaron columnas: {missing}")
                print("   Columnas disponibles:", list(df.columns))
                continue # Salta a la siguiente hoja

            tmp = df[[col_codigo, col_desc, col_inv, col_clas]].copy()
            tmp.columns = ["Codigo", "Descripcion", "Existencia", "Clasificacion"]
            # Sucursal = nombre corto de la hoja
            suc = hoja.replace("Class", "").replace("(", "").replace(")", "").strip()
            tmp["Sucursal"] = suc

            # Todo como texto para evitar None
            for c in ["Codigo", "Descripcion", "Existencia", "Clasificacion", "Sucursal"]:
                tmp[c] = tmp[c].astype(str).fillna("").str.strip()

            frames.append(tmp)
        except Exception as e:
            print(f"❌ Error procesando la hoja {hoja}: {e}")
            print("   Revisa la estructura de esta hoja en tu archivo Excel.")
            # Continuamos con las otras hojas si es posible

    if not frames:
        print("❌ No se pudo construir ningún DataFrame (revisa encabezados de fila 9 y errores anteriores).")
        return # Termina el script

    data = pd.concat(frames, ignore_index=True)
    print(f"✅ Total de registros combinados: {len(data)}")

    # (Re)crear base
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # ---- Tabla NORMAL para LIKE ----
    cur.execute("DROP TABLE IF EXISTS inventario_plain;")
    cur.execute("""
        CREATE TABLE inventario_plain (
            Codigo TEXT,
            Descripcion TEXT,
            Existencia TEXT,
            Clasificacion TEXT,
            Sucursal TEXT
        );
    """)
    cur.executemany(
        "INSERT INTO inventario_plain (Codigo, Descripcion, Existencia, Clasificacion, Sucursal) VALUES (?, ?, ?, ?, ?);",
        data.values.tolist()
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_desc ON inventario_plain(Descripcion);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_cod  ON inventario_plain(Codigo);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_clas ON inventario_plain(Clasificacion);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_inv_suc  ON inventario_plain(Sucursal);")

    # ---- Tabla FTS5 para búsquedas futuras ----
    try:
        cur.execute("DROP TABLE IF EXISTS inventario;")
        cur.execute("""
            CREATE VIRTUAL TABLE inventario USING fts5(
                Codigo, Descripcion, Existencia, Clasificacion, Sucursal, content=''
            );
        """)
        cur.executemany(
            "INSERT INTO inventario (Codigo, Descripcion, Existencia, Clasificacion, Sucursal) VALUES (?, ?, ?, ?, ?);",
            data.values.tolist()
        )
    except Exception as e:
        print(f"⚠️ No se pudo crear la tabla FTS5 (no es crítico): {e}")

    conn.commit()
    conn.close()

    print("✅ Base de datos creada correctamente (tabla normal + FTS).")
    print("✅ Índice creado con éxito.")
    # Las líneas input() han sido eliminadas para que funcione en Render

if __name__ == "__main__":
    main()