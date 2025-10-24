from flask import Flask, request, render_template_string, url_for
import sqlite3

app = Flask(__name__)

TEMPLATE = r"""
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Ferretería El Cedro • Buscador de Inventario</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    :root{
      --azul: #1d4ed8;
      --azul-oscuro: #1e3a8a;
      --azul-claro: #eff6ff;
      --blanco: #ffffff;
      --gris-borde: #e5e7eb;
      --texto: #0f172a;
      --gris-suave: #f9fafb;
    }
    body{ background:var(--gris-suave); color:var(--texto); font-family: 'Inter', sans-serif;}
    .navbar{ background:linear-gradient(90deg, var(--azul-oscuro), var(--azul)); box-shadow:0 4px 10px rgba(0,0,0,.15);}
    .navbar-brand{ font-weight:600;}
    .card{ border:none; border-radius:16px; box-shadow:0 4px 16px rgba(0,0,0,.08);}
    .card-header{ background:var(--azul-claro); color:var(--azul-oscuro); font-weight:600;}
    .table thead th{ background:#e0ecff; color:#1e3a8a; font-weight:600;}
    .btn-primary{ background:var(--azul); border:none; }
    .btn-primary:hover{ background:var(--azul-oscuro);}
    .btn-outline-secondary:hover{ background:var(--azul-claro); color:var(--azul-oscuro);}
    .list-group-item:hover{ background:var(--azul-claro);}
    .sticky-top-card{ position:sticky; top:0.75rem; z-index:1030; }
  </style>
</head>
<body>
  <nav class="navbar navbar-dark mb-4">
    <div class="container-fluid">
      <span class="navbar-brand">Ferretería El Cedro • Buscador de Inventario</span>
    </div>
  </nav>

  <div class="container mb-5">

    <!-- === Tabla de Detalle Arriba === -->
    <div class="card sticky-top-card mb-4">
      <div class="card-header">
        {% if detalle_nombre %}
          <strong>Detalle de:</strong> {{ detalle_nombre }}
        {% else %}
          <strong>Detalle:</strong> <span class="text-muted">Selecciona un producto</span>
        {% endif %}
      </div>
      <div class="card-body p-0">
        <table class="table table-sm mb-0">
          <thead>
            <tr><th>Sucursal</th><th>Existencia</th><th>Clasificación</th></tr>
          </thead>
          <tbody>
            {% if detalle_rows is not none and detalle_rows|length > 0 %}
              {% for s, ex, cl in detalle_rows %}
              <tr><td>{{ s }}</td><td>{{ ex }}</td><td>{{ cl }}</td></tr>
              {% endfor %}
            {% else %}
              <tr><td colspan="3" class="text-center text-muted py-3">Selecciona un producto para ver el detalle</td></tr>
            {% endif %}
          </tbody>
        </table>
      </div>
      <div class="card-footer text-end">
        <a class="btn btn-outline-secondary btn-sm" href="{{ url_for('index', q=q) }}">Limpiar detalle</a>
      </div>
    </div>

    <!-- === Buscador Abajo === -->
    <div class="card">
      <div class="card-body">
        <form method="get" class="row g-2 align-items-center" action="{{ url_for('index') }}">
          <div class="col-md-9">
            <input name="q" class="form-control form-control-lg" placeholder="Buscar producto o código..." value="{{ q or '' }}">
            <div class="form-text">Tip: puedes buscar por varios términos (ej. <code>taladro 1/2 truper</code>)</div>
          </div>
          <div class="col-md-3 d-grid">
            <button class="btn btn-primary btn-lg" type="submit">Buscar</button>
          </div>
        </form>

        <hr>

        {% if results is not none %}
          {% if results|length > 0 %}
            <div class="alert alert-primary">Resultados encontrados: {{ results|length }}</div>
            <div class="list-group">
              {% for cod, desc in results %}
                <a href="{{ url_for('index', q=q, detalle=desc) }}" class="list-group-item list-group-item-action">
                  <div class="d-flex justify-content-between align-items-center">
                    <strong>{{ desc }}</strong>
                    <small class="text-muted">{{ cod }}</small>
                  </div>
                </a>
              {% endfor %}
            </div>
          {% else %}
            <div class="alert alert-warning">Sin resultados.</div>
          {% endif %}
        {% endif %}
      </div>
    </div>

    <div class="text-center text-muted mt-4">
      Hecho para uso interno – Inventario consolidado • Ferretería El Cedro
    </div>
  </div>
</body>
</html>
"""

# ==== FUNCIONES ====

def buscar_productos(conn, q):
    tokens = [t.strip() for t in q.split() if t.strip()]
    if not tokens:
        return []
    where_parts, params = [], []
    for t in tokens:
        where_parts.append("(Descripcion LIKE ? OR Codigo LIKE ?)")
        like = f"%{t}%"
        params.extend([like, like])
    sql = f"""
        SELECT Codigo, Descripcion
        FROM inventario
        WHERE {' AND '.join(where_parts)}
        GROUP BY Codigo, Descripcion
        ORDER BY Descripcion
        LIMIT 100;
    """
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur.fetchall()

def traer_detalle(conn, desc):
    cur = conn.cursor()
    cur.execute("""
        SELECT Sucursal, Existencia, Clasificacion
        FROM inventario
        WHERE Descripcion = ?
        ORDER BY CASE Sucursal
             WHEN 'ADE' THEN 1 WHEN 'EX' THEN 2 WHEN 'Global' THEN 3
             WHEN 'HI' THEN 4 WHEN 'MT' THEN 5 WHEN 'SA' THEN 6 ELSE 99 END;
    """, (desc,))
    return cur.fetchall()

# ==== RUTA PRINCIPAL ====

@app.route("/", methods=["GET"])
def index():
    q = request.args.get("q", "").strip()
    detalle_nombre = request.args.get("detalle", "").strip()
    results, detalle_rows = None, []

    conn = sqlite3.connect("inventario_el_cedro.db")

    if q:
        results = buscar_productos(conn, q)
    if detalle_nombre:
        detalle_rows = traer_detalle(conn, detalle_nombre)

    conn.close()
    return render_template_string(TEMPLATE, q=q, results=results,
                                  detalle_nombre=detalle_nombre, detalle_rows=detalle_rows)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
