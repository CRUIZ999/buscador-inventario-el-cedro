from flask import Flask, request, jsonify, render_template_string
import sqlite3
import html
import os  # Importar OS

app = Flask(__name__)

DB_PATH = "inventario_el_cedro.db"


# ------------------ utilidades DB ------------------
def q(query, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def build_fts_query(user_q: str) -> str:
    """
    Convierte 'tinaco 1100 truper' → 'tinaco* 1100* truper*'
    para usar con FTS5.
    """
    tokens = [t.strip() for t in user_q.split() if t.strip()]
    if not tokens:
        return ""
    return " ".join(f"{t}*" for t in tokens)


# ------------------ plantilla HTML ------------------
TPL = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Ferretería El Cedro • Buscador de Inventario</title>
  <style>
    :root{
      --azul:#1e40af; --azul-2:#2563eb; --azul-claro:#e8f0ff;
      --gris:#475569; --bg:#f5f8ff;
    }
    *{box-sizing:border-box}
    body{margin:0;background:var(--bg);font-family:Segoe UI,system-ui,Arial,sans-serif}
    header{background:linear-gradient(90deg,var(--azul),var(--azul-2));color:#fff;padding:16px 28px;font-weight:700;font-size:20px;box-shadow:0 2px 6px rgba(0,0,0,.18)}
    .wrap{max-width:1100px;margin:32px auto;background:#fff;border-radius:12px;padding:22px 28px;box-shadow:0 6px 14px rgba(0,0,0,.08)}
    h3{margin:6px 0 14px 0;color:var(--azul)}
    table{width:100%;border-collapse:collapse;margin-top:6px}
    th{background:var(--azul-claro);color:var(--azul);text-align:left;padding:10px}
    td{padding:10px;border-bottom:1px solid #f1f5f9}
    .search{display:flex;gap:12px;margin-top:18px}
    .search input{flex:1;padding:12px 14px;border:1px solid #cbd5e1;border-radius:8px;font-size:16px}
    .btn{background:var(--azul);color:#fff;border:none;border-radius:8px;padding:12px 18px;font-size:16px;cursor:pointer}
    .btn:hover{background:var(--azul-2)}
    .item{padding:10px 6px;border-bottom:1px solid #eef2f7;cursor:pointer}
    .item b{color:#0f172a}
    .nores{background:#fff7ed;color:#92400e;padding:10px;border-radius:8px;margin-top:12px}
    .foot{margin:36px 0 6px 0;text-align:center;color:var(--gris);font-size:14px}
    .badge{color:#0f172a}
  </style>
</head>
<body>
<header>Ferretería El Cedro • Buscador de Inventario</header>

<div class="wrap">
  <h3>🔹 Detalle:
    {% if detalle %}
      {{ detalle }}
    {% else %}
      Selecciona un producto
    {% endif %}
  </h3>

  <table>
    <thead>
      <tr><th>Sucursal</th><th>Existencia</th><th>Clasificación</th></tr>
    </thead>
    <tbody>
      {% if detalle_rows %}
        {% for r in detalle_rows %}
          <tr>
            <td>{{ r['Sucursal'] }}</td>
            <td>{{ r['Existencia'] }}</td>
            <td>{{ r['Clasificacion'] }}</td>
          </tr>
        {% endfor %}
      {% else %}
        <tr><td colspan="3">Selecciona un producto para ver el detalle por sucursal</td></tr>
      {% endif %}
    </tbody>
  </table>

  <form method="get" class="search">
    <input type="text" name="q" placeholder="Buscar producto o código..." value="{{ query or '' }}">
    <button class="btn" type="submit">Buscar</button>
  </form>

  {% if resultados %}
    <div style="margin-top:10px">
      {% for r in resultados %}
        <div class="item" onclick="sel('{{ r['Descripcion']|e }}')">
          <b>{{ r['Descripcion'] }}</b>
          <span class="badge">— {{ r['Codigo'] }}</span>
        </div>
      {% endfor %}
    </div>
  {% elif query %}
    <div class="nores">Sin resultados.</div>
  {% endif %}
</div>

<div class="foot">Hecho para uso interno – Inventario consolidado • Ferretería El Cedro</div>

<script>
  function sel(nombre){
    location.href='/?detalle='+encodeURIComponent(nombre);
  }
</script>
</body>
</html>
"""


# ------------------ rutas ------------------
@app.route("/")
def home():
    query = request.args.get("q", "", type=str).strip()
    detalle = request.args.get("detalle", "", type=str).strip()

    resultados = []
    detalle_rows = []

    # --- búsqueda por FTS ---
    if query:
        fts = build_fts_query(query)
        if fts:
            resultados = q(
                """
                SELECT Codigo, Descripcion
                FROM inventario_plain
                WHERE Codigo IN (
                    SELECT Codigo
                    FROM inventario
                    WHERE Descripcion MATCH ? 
                )
                LIMIT 30
                """,
                (fts,),
            )

    # --- detalle por sucursal ---
    if detalle:
        detalle_rows = q(
            """
            SELECT Sucursal, Existencia, Clasificacion
            FROM inventario_plain
            WHERE Descripcion LIKE ?
            """,
            (f"%{detalle}%",),
        )

    return render_template_string(
        TPL,
        query=query,
        detalle=detalle,
        resultados=resultados,
        detalle_rows=detalle_rows,
    )

    # --- detalle por sucursal ---
    if detalle:
        detalle_rows = q(
            """
            SELECT Sucursal, Existencia, Clasificacion
            FROM inventario_plain
            WHERE Descripcion LIKE ?
            """,
            (f"%{detalle}%",),
        )

    return render_template_string(
        TPL,
        query=query,
        detalle=detalle,
        resultados=resultados,
        detalle_rows=detalle_rows,
    )


# --- NUEVA VERSIÓN MEJORADA de endpoints de depuración ---
@app.route("/debug_db")
def debug_db():
    try:
        # 1. Contar filas en la TABLA DE DATOS
        r1 = q("SELECT COUNT(*) AS c FROM inventario_plain")
        
        # 2. Contar filas en la TABLA DE BÚSQUEDA (FTS)
        r2 = q("SELECT COUNT(*) AS c FROM inventario")

        # 3. Comprobar que la tabla FTS existe
        r3 = q("SELECT name FROM sqlite_master WHERE type='table' AND name='inventario'")

        return jsonify({
            "filas_en_tabla_datos_plain": r1[0]["c"] if r1 else -1,
            "filas_en_tabla_busqueda_fts": r2[0]["c"] if r2 else -1,
            "existe_tabla_fts": bool(r3),
        })
    except Exception as e:
        # Si 'inventario' o 'inventario_plain' no existen, esto atrapará el error
        return jsonify({"error": str(e)}), 500


@app.route("/debug_sample")
def debug_sample():
    try:
        sample = q("SELECT Codigo, Descripcion, Existencia, Clasificacion, Sucursal FROM inventario_plain LIMIT 10")
        return jsonify({"sample": [dict(r) for r in sample]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- ejecución (corregida para Render) ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
