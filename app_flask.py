from flask import Flask, request, jsonify, render_template_string
import sqlite3
import html
import os

app = Flask(__name__)

DB_PATH = "inventario_el_cedro.db"


# ------------------ utilidades DB ------------------
def q(query, params=()):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error en la base de datos: {e}")
        return []

def build_fts_query(user_q: str) -> str:
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
  <h3 id="detalle-titulo">🔹 Detalle:
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
    <tbody id="detalle-tbody">
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
  async function sel(nombre) {
    // 1. Obtener los elementos del DOM
    const titulo = document.getElementById('detalle-titulo');
    const tbody = document.getElementById('detalle-tbody');

    // 2. Actualizar el título y mostrar estado de "cargando"
    titulo.innerText = '🔹 Detalle: ' + nombre;
    tbody.innerHTML = '<tr><td colspan="3">Cargando...</td></tr>';

    try {
      // 3. Llamar a la nueva API para obtener los datos
      const response = await fetch('/api/detalle?nombre=' + encodeURIComponent(nombre));
      if (!response.ok) {
        throw new Error('Error de red');
      }
      const filas = await response.json();

      // 4. Limpiar la tabla
      tbody.innerHTML = '';

      // 5. Mostrar resultados o mensaje de "sin resultados"
      if (filas.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3">No se encontraron detalles para este producto.</td></tr>';
        return;
      }

      // 6. Llenar la tabla con las nuevas filas
      for (const r of filas) {
        const tr = document.createElement('tr');
        
        const tdSuc = document.createElement('td');
        tdSuc.innerText = r.Sucursal;
        tr.appendChild(tdSuc);
        
        const tdExi = document.createElement('td');
        tdExi.innerText = r.Existencia;
        tr.appendChild(tdExi);
        
        const tdCla = document.createElement('td');
        tdCla.innerText = r.Clasificacion;
        tr.appendChild(tdCla);

        tbody.appendChild(tr);
      }

    } catch (error) {
      console.error('Error al cargar detalle:', error);
      tbody.innerHTML = '<tr><td colspan="3">Error al cargar los datos.</td></tr>';
    }
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

    try:
        # Búsqueda con LIKE (segura) y DISTINCT (sin duplicados)
        if query:
            like_query = f"%{query}%"
            resultados = q(
                """
                SELECT DISTINCT Codigo, Descripcion
                FROM inventario_plain
                WHERE Descripcion LIKE ? OR Codigo LIKE ?
                LIMIT 30
                """,
                (like_query, like_query),
            )

        # Esto solo se usa para la CARGA INICIAL de la página
        if detalle:
            detalle_rows = q(
                """
                SELECT Sucursal, Existencia, Clasificacion
                FROM inventario_plain
                WHERE Descripcion = ?
                """,
                (detalle,),
            )
        
        return render_template_string(
            TPL,
            query=query,
            detalle=detalle,
            resultados=resultados,
            detalle_rows=detalle_rows,
        )
    except Exception as e:
        return f"<h1>Error Crítico en la App</h1><p>{str(e)}</p>", 500


# --- CAMBIO 4: Nueva ruta de API ---
@app.route("/api/detalle")
def api_detalle():
    nombre = request.args.get("nombre", "", type=str).strip()
    
    if not nombre:
        return jsonify({"error": "No se proporcionó nombre"}), 400

    # Usamos la consulta exacta (el 'nombre' viene del clic)
    detalle_rows = q(
        """
        SELECT Sucursal, Existencia, Clasificacion
        FROM inventario_plain
        WHERE Descripcion = ?
        """,
        (nombre,),
    )
    
    # Convertimos los resultados a una lista de diccionarios para JSON
    return jsonify([dict(r) for r in detalle_rows])


# --- endpoints de depuración (sin cambios) ---
@app.route("/debug_db")
def debug_db():
    try:
        r1 = q("SELECT COUNT(*) AS c FROM inventario_plain")
        r2 = q("SELECT COUNT(*) AS c FROM inventario")
        r3 = q("SELECT name FROM sqlite_master WHERE type='table' AND name='inventario'")
        return jsonify({
            "filas_en_tabla_datos_plain": r1[0]["c"] if r1 else -1,
            "filas_en_tabla_busqueda_fts": r2[0]["c"] if r2 else -1,
            "existe_tabla_fts": bool(r3),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/debug_sample")
def debug_sample():
    try:
        sample = q("SELECT Codigo, Descripcion, Existencia, Clasificacion, Sucursal FROM inventario_plain LIMIT 10")
        return jsonify({"sample": [dict(r) for r in sample]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- ejecución (sin cambios) ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)