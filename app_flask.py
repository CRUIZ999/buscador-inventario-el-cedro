from flask import Flask, render_template_string, request
import sqlite3

app = Flask(__name__)

TEMPLATE = """
<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <title>Ferretería El Cedro • Buscador de Inventario</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
  </head>
  <body class="bg-light">
    <nav class="navbar navbar-dark bg-success mb-4">
      <div class="container-fluid">
        <span class="navbar-brand mb-0 h1">Ferretería El Cedro • Buscador de Inventario</span>
      </div>
    </nav>

    <div class="container">
      <form method="get" class="mb-4">
        <div class="input-group">
          <input name="q" type="text" class="form-control" placeholder="Buscar producto o código..." value="{{ q|default('') }}">
          <button class="btn btn-success" type="submit">Buscar</button>
        </div>
        <div class="form-text">Tip: puedes teclear varios términos (ej. <code>taladro 1/2 truper</code>)</div>
      </form>

      {% if not detalle and results %}
        <div class="alert alert-success">Productos encontrados: {{ results|length }}</div>
        <ul class="list-group">
          {% for desc in results %}
            <li class="list-group-item d-flex justify-content-between align-items-center">
              <a href="/?detalle={{ desc|urlencode }}" class="text-decoration-none">{{ desc }}</a>
              <span class="badge bg-success">Ver detalle</span>
            </li>
          {% endfor %}
        </ul>
      {% endif %}

      {% if detalle %}
        <div class="alert alert-info">Detalle de: <b>{{ detalle }}</b></div>
        {% if rows %}
          <table class="table table-bordered table-striped table-sm">
            <thead class="table-success">
              <tr>
                <th>Sucursal</th>
                <th>Existencia</th>
                <th>Clasificación</th>
              </tr>
            </thead>
            <tbody>
              {% for r in rows %}
              <tr>
                <td>{{ r[0] }}</td>
                <td>{{ r[1] }}</td>
                <td>{{ r[2] }}</td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
          <a href="/" class="btn btn-outline-success">← Nueva búsqueda</a>
        {% else %}
          <div class="alert alert-warning">Sin información disponible.</div>
        {% endif %}
      {% endif %}

      {% if q and not results and not detalle %}
        <div class="alert alert-warning">Sin resultados.</div>
      {% endif %}

      <div class="text-center mt-5 text-muted">
        Hecho para uso interno – Inventario consolidado • Ferretería El Cedro
      </div>
    </div>
  </body>
</html>
"""

# Función: busca productos únicos por descripción
def search_products(q):
    tokens = [t.strip() for t in q.split() if t.strip()]
    if not tokens:
        return []

    conn = sqlite3.connect("inventario_el_cedro.db")
    cur = conn.cursor()

    clauses = []
    params = []
    for t in tokens:
        like = f"%{t}%"
        clauses.append("(Descripcion LIKE ? OR Codigo LIKE ? OR Clasificacion LIKE ?)")
        params.extend([like, like, like])

    where_sql = " AND ".join(clauses)
    sql = f"SELECT DISTINCT Descripcion FROM inventario_plain WHERE {where_sql} ORDER BY Descripcion LIMIT 200;"
    cur.execute(sql, params)
    results = [r[0] for r in cur.fetchall()]
    conn.close()
    return results

# Función: busca existencias por sucursal
def detalle_producto(descripcion):
    conn = sqlite3.connect("inventario_el_cedro.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT Sucursal, Existencia, Clasificacion
        FROM inventario_plain
        WHERE Descripcion = ?
        ORDER BY Sucursal;
    """, (descripcion,))
    rows = cur.fetchall()
    conn.close()
    return rows

@app.route("/", methods=["GET"])
def index():
    q = request.args.get("q", "").strip()
    detalle = request.args.get("detalle")
    results = None
    rows = None

    if detalle:
        rows = detalle_producto(detalle)
    elif q:
        results = search_products(q)

    return render_template_string(TEMPLATE, q=q, results=results, detalle=detalle, rows=rows)

if __name__ == "__main__":
    app.run(port=8000, debug=False)

