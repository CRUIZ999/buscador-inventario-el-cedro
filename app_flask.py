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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root{
      --c-bg:         #f5f8ff;
      --c-surface:    #ffffff;
      --c-primary:    #1d4ed8; /* azul principal */
      --c-primary-700:#1e40af;
      --c-primary-50: #eff6ff;
      --c-border:     #e6ebf5;
      --c-text:       #0f172a;
      --c-muted:      #64748b;
      --c-accent:     #60a5fa;
      --shadow-1:     0 6px 20px rgba(29,78,216,.08);
      --shadow-2:     0 10px 30px rgba(29,78,216,.12);
    }

    html,body{background:var(--c-bg); color:var(--c-text); font-family:"Inter", system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial, "Noto Sans", "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";}

    /* Navbar */
    .nav-glass{
      background: linear-gradient(90deg, #1e3a8a 0%, #1d4ed8 60%, #2563eb 100%);
      box-shadow: var(--shadow-2);
    }
    .brand{
      font-weight:700; letter-spacing:.3px;
    }

    /* Contenedores */
    .container-narrow{max-width: 1080px;}

    /* Cards */
    .card{
      border: 1px solid var(--c-border);
      border-radius: 16px;
      overflow: hidden;
      box-shadow: var(--shadow-1);
      background: var(--c-surface);
    }
    .card-header{
      background: linear-gradient(180deg, var(--c-primary-50), #fff);
      border-bottom: 1px solid var(--c-border);
      font-weight: 600;
      color: var(--c-primary-700);
    }
    .card-footer{
      background:#fff;
      border-top:1px solid var(--c-border);
    }

    /* Tabla de detalle */
    table thead th{
      background: #e7f0ff;
      color: #113a8f;
      font-weight:600;
      border-bottom: 1px solid var(--c-border);
    }
    table tbody tr:nth-child(even){
      background: #fafcff;
    }

    /* Botones */
    .btn-primary{
      background: var(--c-primary);
      border-color: var(--c-primary);
      font-weight:600;
      box-shadow: 0 6px 12px rgba(29,78,216,.16);
    }
    .btn-primary:hover{
      background: var(--c-primary-700);
      border-color: var(--c-primary-700);
      box-shadow: 0 8px 16px rgba(29,78,216,.24);
    }
    .btn-outline-secondary{
      border-color: #cfd8ea; color:#385192; font-weight:600;
    }
    .btn-outline-secondary:hover{
      background:#eef4ff; color:#163c91; border-color:#becbe6;
    }

    /* Inputs */
    .form-control{
      border-radius: 12px; border:1px solid var(--c-border);
    }
    .form-control:focus{
      border-color: var(--c-accent);
      box-shadow: 0 0 0 .25rem rgba(96,165,250,.25);
    }

    /* Resultados */
    .list-group-item{
      border:1px solid var(--c-border);
      border-radius: 12px !important;
      margin-bottom:.5rem;
      transition: transform .08s ease, box-shadow .12s ease, border-color .12s ease;
    }
    .list-group-item:hover{
      transform: translateY(-1px);
      border-color:#c7d5f7;
      box-shadow: var(--shadow-1);
      background:#f4f8ff;
    }
    .item-code{
      color: var(--c-muted);
      font-weight:600;
    }

    /* sticky detalle arriba */
    .sticky-top-card{ position:sticky; top:0.75rem; z-index:1030; }

    .muted{ color:var(--c-muted); }
  </style>
</head>
<body>
  <!-- NAV -->
  <nav class="navbar nav-glass navbar-dark mb-4">
    <div class="container container-narrow">
      <span class="navbar-brand brand">Ferretería El Cedro • Buscador de Inventario</span>
    </div>
  </nav>

  <div class="container container-narrow mb-5">

    <!-- =========== DETALLE ARRIBA (STICKY) =========== -->
    <div class="card sticky-top-card mb-4">
      <div class="card-header py-3 px-4">
        {% if detalle_nombre %}
          <span>Detalle de:</span>
          <span class="ms-1 text-primary-emphasis">{{ detalle_nombre }}</span>
        {% else %}
          <span>Detalle: <span class="muted">selecciona un producto</span></span>
        {% endif %}
      </div>

      <div class="card-body p-0">
        <table class="table table-sm mb-0">
          <thead>
            <tr>
              <th style="width:28%">Sucursal</th>
              <th style="width:18%">Existencia</th>
              <th>Clasificación</th>
            </tr>
          </thead>
          <tbody id="detalle-tbody">
            {% if detalle_rows and detalle_rows|length > 0 %}
              {% for s, ex, cl in detalle_rows %}
              <tr>
                <td class="py-2 px-3">{{ s }}</td>
                <td class="py-2 px-3">{{ ex }}</td>
                <td class="py-2 px-3">{{ cl }}</td>
              </tr>
              {% endfor %}
            {% else %}
              <tr>
                <td colspan="3" class="text-center muted py-3">
                  Selecciona un producto para ver el detalle por sucursal
                </td>
              </tr>
            {% endif %}
          </tbody>
        </table>
      </div>

      <div class="card-footer d-flex justify-content-end">
        <a class="btn btn-outline-secondary btn-sm" href="{{ url_for('index', q=q) }}">Limpiar detalle</a>
      </div>
    </div>

    <!-- =========== BUSCADOR ABAJO =========== -->
    <div class="card">
      <div class="card-body">
        <form class="row g-2 align-items-center" method="get" action="{{ url_for('index') }}">
          <div class="col-12 col-md-9">
            <input type="text" class="form-control form-control-lg"
                   name="q" placeholder="Buscar producto o código..."
                   value="{{ q or '' }}" autofocus>
            <div class="form-text">
              Tip: puedes teclear varios términos (ej. <code>taladro 1/2 truper</code>)
            </div>
          </div>
          <div class="col-12 col-md-3 d-grid d-md-flex justify-content-md-end">
            <button class="btn btn-primary btn-lg px-4" type="submit">Buscar</button>
          </div>
        </form>

        <hr class="my-4">

        {% if results is not None %}
          {% if results|length > 0 %}
            <div class="alert alert-primary py-2 mb-3" style="background:var(--c-primary-50); border:1px solid #d5e5ff;">
              Resultados encontrados: <strong>{{ results|length }}</strong>
            </div>

            <div class="list-group">
              {% for cod, desc in results %}
                <a class="list-group-item list-group-item-action"
                   href="{{ url_for('index', q=q, detalle=desc) }}">
                  <div class="d-flex w-100 justify-content-between">
                    <div class="fw-semibold">{{ desc }}</div>
                    <small class="item-code">{{ cod }}</small>
                  </div>
                </a>
              {% endfor %}
            </div>
          {% else %}
            <div class="alert alert-warning mb-0">Sin resultados.</div>
          {% endif %}
        {% endif %}
      </div>
    </div>

    <div class="text-center mt-4 muted">
      Hecho para uso interno – Inventario consolidado • Ferretería El Cedro
    </div>

  </div>
</body>
</html>
"""

# ------------------ Lógica de datos ------------------ #

def buscar_productos_sin_fts(conn, q):
    """
    Búsqueda robusta por LIKE (sin FTS).
    Separa q en tokens y exige que TODAS aparezcan en (Descripcion O Codigo).
    Devuelve productos únicos (Codigo, Descripcion).
    """
    tokens = [t.strip() for t in q.split() if t.strip()]
    if not tokens:
        return []

    where_parts = []
    params = []
    for t in tokens:
        where_parts.append("(Descripcion LIKE ? OR Codigo LIKE ?)")
        like = f"%{t}%"
        params.extend([like, like])

    where_sql = " AND ".join(where_parts)

    sql = f"""
        SELECT Codigo, Descripcion
        FROM inventario
        WHERE {where_sql}
        GROUP BY Codigo, Descripcion
        ORDER BY Descripcion
        LIMIT 100;
    """
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur.fetchall()


def traer_detalle_por_descripcion(conn, descripcion):
    """
    Devuelve (Sucursal, Existencia, Clasificacion) para una Descripcion exacta.
    Ordena sucursales en un orden práctico.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT Sucursal, Existencia, Clasificacion
        FROM inventario
        WHERE Descripcion = ?
        ORDER BY CASE Sucursal
             WHEN 'ADE' THEN 1
             WHEN 'EX'  THEN 2
             WHEN 'Global' THEN 3
             WHEN 'HI' THEN 4
             WHEN 'MT' THEN 5
             WHEN 'SA' THEN 6
             ELSE 99
        END, Sucursal;
    """, (descripcion,))
    return cur.fetchall()


@app.route("/", methods=["GET"])
def index():
    q = request.args.get("q", "").strip()
    detalle_nombre = request.args.get("detalle", "").strip()

    results = None
    detalle_rows = []

    conn = sqlite3.connect("inventario_el_cedro.db")

    # Lista de productos
    if q:
        try:
            results = buscar_productos_sin_fts(conn, q)
        except Exception:
            results = []

    # Detalle por sucursal
    if detalle_nombre:
        try:
            detalle_rows = traer_detalle_por_descripcion(conn, detalle_nombre)
        except Exception:
            detalle_rows = []

    conn.close()

    return render_template_string(
        TEMPLATE,
        q=q,
        results=results,
        detalle_nombre=detalle_nombre,
        detalle_rows=detalle_rows
    )

if __name__ == "__main__":
  app.run(host="0.0.0.0", port=8000, debug=False)
