# app_flask.py
from flask import Flask, render_template_string, request, jsonify, redirect, url_for
import sqlite3
import unicodedata
import urllib.parse

app = Flask(__name__)

DB_PATH = "inventario_el_cedro.db"


# ------------------------------
# Utilidades de normalización
# ------------------------------
def _normalize(s: str) -> str:
    """Quita acentos, pone en minúsculas y normaliza ñ/ü para comparación flexible."""
    if not s:
        return ""
    s = s.lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")  # sin tildes
    s = s.replace("ñ", "n").replace("ü", "u")
    return s


def _san_sql_expr(col: str) -> str:
    """
    Devuelve una expresión SQL que emula 'unaccent + lower' en SQLite.
    Convierte áéíóúü/ñ en aeiouu/n y aplica lower(col).
    """
    return (
        f"replace(replace(replace(replace(replace("
        f"replace(replace(lower({col}), 'á','a'),'é','e'),'í','i'),'ó','o'),'ú','u'),'ü','u'),'ñ','n')"
    )


# ------------------------------
# Capa de datos
# ------------------------------
def buscar_productos(term: str):
    """
    Búsqueda tolerante:
    - Divide la consulta en tokens por espacios.
    - Cada token debe aparecer en AL MENOS una de las columnas (AND entre tokens).
    - Coincidencia por subcadena con LIKE %token%.
    - Ignora acentos/mayúsculas.
    - Columnas: Descripcion, Codigo, Clasificacion, Sucursal.
    """
    term = (term or "").strip()
    if not term:
        return []

    tokens = [_normalize(t) for t in term.split() if t.strip()]
    if not tokens:
        return []

    cols = ["Descripcion", "Codigo", "Clasificacion", "Sucursal"]

    # (col LIKE ? OR col2 LIKE ? ...) por token
    per_token_clauses = []
    params = []
    for tk in tokens:
        like = f"%{tk}%"
        group = " OR ".join([f"{_san_sql_expr(c)} LIKE ?" for c in cols])
        per_token_clauses.append(f"({group})")
        params.extend([like] * len(cols))

    where = " AND ".join(per_token_clauses)

    sql = f"""
        SELECT Codigo, Descripcion, Existencia, Clasificacion, Sucursal
        FROM inventario
        WHERE {where}
        LIMIT 50;
    """

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def obtener_detalle_por_descripcion(descripcion: str):
    """
    Devuelve el detalle por sucursal para una descripción. Comparación flexible
    (sin acentos, minúsculas y normalizando ñ/ü).
    """
    desc_norm = _normalize(descripcion)
    if not desc_norm:
        return []

    sql = f"""
        SELECT Sucursal, COALESCE(Existencia, 0) AS Existencia, Clasificacion
        FROM inventario
        WHERE {_san_sql_expr('Descripcion')} = ?
        ORDER BY 
            CASE Sucursal
                WHEN 'HI' THEN 1
                WHEN 'EX' THEN 2
                WHEN 'MT' THEN 3
                WHEN 'SA' THEN 4
                WHEN 'ADE' THEN 5
                WHEN 'Global' THEN 6
                ELSE 7
            END, Sucursal;
    """

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql, (desc_norm,))
    rows = cur.fetchall()
    conn.close()
    return rows


# ------------------------------
# Plantilla (tema azul/blanco)
# ------------------------------
TEMPLATE = r"""
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Ferretería El Cedro • Buscador de Inventario</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <!-- Bootstrap -->
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    :root{
      --azul-800:#1e3a8a;
      --azul-700:#1d4ed8;
      --azul-600:#2563eb;
      --azul-100:#e0e7ff;
      --gris-50:#f8fafc;
      --gris-100:#f1f5f9;
      --gris-300:#cbd5e1;
    }
    body{ background: var(--gris-50); }
    .navbar{
      background: linear-gradient(90deg, var(--azul-800), var(--azul-600));
    }
    .navbar .navbar-brand{ color:#fff; font-weight:600; }
    .card{
      border:1px solid var(--gris-300);
      box-shadow: 0 8px 16px rgba(30,58,138,.06);
    }
    .table thead th{
      background: var(--azul-100);
      color: #0f172a;
    }
    .btn-cedro{
      background: var(--azul-700);
      color: #fff;
      border: none;
    }
    .btn-cedro:hover{ background: var(--azul-600); }
    .pill{
      border-radius: 9999px;
      padding: .15rem .6rem;
      font-size: .85rem;
    }
    .list-hover .list-group-item{
      cursor:pointer;
    }
    .list-hover .list-group-item:hover{
      background: #f8fafc;
    }
  </style>
</head>
<body>

<nav class="navbar navbar-expand">
  <div class="container">
    <span class="navbar-brand">Ferretería El Cedro • Buscador de Inventario</span>
  </div>
</nav>

<div class="container my-4">

  <!-- Detalle arriba -->
  <div class="card mb-4">
    <div class="card-body">
      <div class="d-flex justify-content-between align-items-center">
        <h6 class="mb-3">
          <span class="text-muted">Detalle:</span>
          {% if detalle_sel %}
            <strong class="ms-1">{{ detalle_sel }}</strong>
          {% else %}
            Selecciona un producto
          {% endif %}
        </h6>
        <a class="btn btn-sm btn-outline-secondary" href="{{ url_for('index') }}">Limpiar detalle</a>
      </div>

      <div class="table-responsive">
        <table class="table table-sm align-middle">
          <thead>
            <tr>
              <th>Sucursal</th>
              <th>Existencia</th>
              <th>Clasificación</th>
            </tr>
          </thead>
          <tbody id="detalle-body">
          {% if detalle_rows and detalle_rows|length>0 %}
            {% for r in detalle_rows %}
              <tr>
                <td>{{ r['Sucursal'] }}</td>
                <td>{{ r['Existencia'] }}</td>
                <td>
                  {% if r['Clasificacion'] %}
                    <span class="pill bg-light border">{{ r['Clasificacion'] }}</span>
                  {% else %}
                    <span class="text-muted">—</span>
                  {% endif %}
                </td>
              </tr>
            {% endfor %}
          {% else %}
            <tr>
              <td colspan="3" class="text-center text-muted py-3">
                Selecciona un producto para ver el detalle por sucursal
              </td>
            </tr>
          {% endif %}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Buscador -->
  <div class="card">
    <div class="card-body">
      <form method="get" id="form-buscar" class="row g-2 align-items-stretch">
        <div class="col-lg-9 col-md-8">
          <input type="text" class="form-control form-control-lg" name="q" id="q"
                 placeholder="Buscar producto o código..." value="{{ q or '' }}" autocomplete="off">
          <div class="form-text">
            Tip: busca varios términos (ej. <code>tinaco truper</code>) • Sin acentos es OK.
          </div>
        </div>
        <div class="col-lg-3 col-md-4 d-grid">
          <button class="btn btn-cedro btn-lg" type="submit">Buscar</button>
        </div>

        <!-- Campo oculto para 'detalle' cuando haces clic en un resultado -->
        <input type="hidden" name="detalle" id="detalle">
      </form>

      <!-- Resultados -->
      <div class="mt-3">
      {% if results is not none %}
        {% if results and results|length>0 %}
          <div class="list-group list-hover">
          {% for r in results %}
            <a class="list-group-item list-group-item-action"
               onclick="seleccionarDetalle('{{ r['Descripcion']|replace(\"'\",\"\\'\")|replace('\"','&quot;') }}')">
              <div class="d-flex justify-content-between">
                <div>
                  <strong>{{ r['Descripcion'] }}</strong>
                  <div class="small text-muted">
                    Código: {{ r['Codigo'] }} • Sucursal: {{ r['Sucursal'] }} • Clasificación: {{ r['Clasificacion'] or '—' }}
                  </div>
                </div>
                <div class="text-end">
                  <span class="pill bg-light border">Exist: {{ r['Existencia'] }}</span>
                </div>
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
  </div>

  <div class="text-center text-muted mt-4">
    Hecho para uso interno – Inventario consolidado • Ferretería El Cedro
  </div>
</div>

<script>
  function seleccionarDetalle(desc) {
    // Rellena el hidden 'detalle' y re-envía el formulario para mostrar el detalle arriba
    document.getElementById('detalle').value = desc;
    document.getElementById('form-buscar').submit();
  }
</script>

</body>
</html>
"""


# ------------------------------
# Rutas
# ------------------------------
@app.route("/", methods=["GET"])
def index():
    q = (request.args.get("q") or "").strip()
    detalle = (request.args.get("detalle") or "").strip()

    results = buscar_productos(q) if q else None

    detalle_rows = []
    detalle_sel = None
    if detalle:
        detalle_sel = detalle
        detalle_rows = obtener_detalle_por_descripcion(detalle)

    return render_template_string(
        TEMPLATE,
        q=q,
        results=results,
        detalle_sel=detalle_sel,
        detalle_rows=detalle_rows,
    )


# ---- Endpoints de depuración opcionales ----
@app.route("/debug_db")
def debug_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM inventario;")
        rows = cur.fetchone()[0]
        # Probar existencia de la tabla
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='inventario';"
        )
        exists = cur.fetchone() is not None
        conn.close()
        return jsonify(rows=rows, table_inventario=exists)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route("/debug_sample")
def debug_sample():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT Codigo, Descripcion, Existencia, Clasificacion, Sucursal FROM inventario LIMIT 10;"
        )
        data = cur.fetchall()
        conn.close()
        return jsonify(sample=data)
    except Exception as e:
        return jsonify(error=str(e)), 500


# ------------------------------
# WSGI / local
# ------------------------------
if __name__ == "__main__":
    # Local
    app.run(host="0.0.0.0", port=8000, debug=True)

