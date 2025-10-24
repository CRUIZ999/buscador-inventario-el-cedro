from flask import Flask, request, render_template_string, jsonify, abort
import sqlite3
import html
import unicodedata

app = Flask(__name__)
DB_PATH = "inventario_el_cedro.db"

# -------------------- Normalización (acentos) -------------------- #
def _normalize(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    # NFD separa letras y acentos; removemos todos los "Mn" (marcas)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower()

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    # Registramos función SQL ufn_norm(text) disponible en consultas
    conn.create_function("ufn_norm", 1, _normalize)
    return conn

# -------------------- Consultas -------------------- #
def buscar_productos(conn, q):
    """
    Búsqueda insensible a acentos y mayúsculas.
    Menos estricta: usa OR entre tokens (coincide si aparece cualquiera).
    """
    tokens = [t.strip() for t in q.split() if t.strip()]
    if not tokens:
        return []

    where_parts, params = [], []
    for t in tokens:
        like = f"%{t}%"
        # Normalizamos columna y patrón con ufn_norm()
        where_parts.append("(ufn_norm(Descripcion) LIKE ufn_norm(?) OR ufn_norm(Codigo) LIKE ufn_norm(?))")
        params.extend([like, like])

    sql = f"""
        SELECT Codigo, Descripcion
        FROM inventario
        WHERE {' OR '.join(where_parts)}
        GROUP BY Codigo, Descripcion
        ORDER BY Descripcion
        LIMIT 100;
    """
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur.fetchall()

def detalle_por_producto(conn, codigo=None, descripcion=None):
    """
    Detalle por sucursal. Usamos preferentemente el código (exacto).
    """
    cur = conn.cursor()
    if codigo:
        cur.execute("""
            SELECT Sucursal, Existencia, Clasificacion
            FROM inventario
            WHERE Codigo = ?
            ORDER BY Sucursal;
        """, (codigo,))
    elif descripcion:
        # Si quisieras también por descripción sin acentos:
        cur.execute("""
            SELECT Sucursal, Existencia, Clasificacion
            FROM inventario
            WHERE ufn_norm(Descripcion) = ufn_norm(?)
            ORDER BY Sucursal;
        """, (descripcion,))
    else:
        return []
    return cur.fetchall()

# -------------------- Plantilla -------------------- #
TEMPLATE = r"""
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Ferretería El Cedro • Buscador de Inventario</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    :root{
      --azul-800:#0f3d8a;
      --azul-700:#1956c1;
      --azul-600:#2563eb;
      --azul-100:#e9f0ff;
      --gris-50:#f8fafc;
    }
    body{background:var(--gris-50);}
    .navbar{background:linear-gradient(90deg,var(--azul-800),var(--azul-600));}
    .navbar-brand{font-weight:700; letter-spacing:.2px;}
    .card{border-radius:14px; box-shadow:0 6px 18px rgba(16,24,40,.06);}
    .table thead th{
      background:var(--azul-100)!important;
      color:#0f172a; border-bottom:1px solid #dbeafe;
    }
    .btn-primary{
      background:var(--azul-700); border-color:var(--azul-700);
    }
    .btn-primary:hover{background:#144aa5; border-color:#144aa5;}
    .result-item{
      padding:.6rem .75rem; border-radius:10px; border:1px solid #e6eefc;
      cursor:pointer; background:white;
    }
    .result-item:hover{background:#f3f7ff; border-color:#d2e2ff;}
    .muted{color:#64748b; font-size:.925rem;}
    .badge-code{font-family:ui-monospace, monospace; background:#eef2ff; color:#1e40af;}
  </style>
</head>
<body>
  <nav class="navbar navbar-dark">
    <div class="container">
      <span class="navbar-brand">Ferretería El Cedro • Buscador de Inventario</span>
    </div>
  </nav>

  <main class="container my-4">

    <!-- Tarjeta de detalle -->
    <div class="card mb-4">
      <div class="card-body">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h6 class="m-0"><strong>Detalle:</strong> <span id="detalle-titulo">Selecciona un producto</span></h6>
          <button id="btn-limpiar" class="btn btn-outline-secondary btn-sm">Limpiar detalle</button>
        </div>
        <div class="table-responsive">
          <table class="table table-sm align-middle">
            <thead>
              <tr>
                <th class="w-25">Sucursal</th>
                <th class="w-25">Existencia</th>
                <th>Clasificación</th>
              </tr>
            </thead>
            <tbody id="detalle-rows">
              <tr>
                <td colspan="3" class="text-center text-muted">
                  Selecciona un producto para ver el detalle por sucursal
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Buscador -->
    <div class="card">
      <div class="card-body">
        <form method="get" class="row g-2">
          <div class="col-md-9">
            <input name="q" value="{{ q }}" class="form-control form-control-lg"
                   placeholder="Buscar producto o código..." />
            <div class="form-text">Tip: busca varios términos (ej. <code>tinaco truper</code>) • Sin acentos es OK.</div>
          </div>
          <div class="col-md-3 d-grid">
            <button class="btn btn-primary btn-lg" type="submit">Buscar</button>
          </div>
        </form>

        {% if results is not none %}
          {% if results %}
            <div class="mt-3">
              <div class="muted mb-2">Resultados (clic para ver detalle):</div>
              <div class="row g-2">
                {% for cod, desc in results %}
                  <div class="col-md-6">
                    <div class="result-item" data-codigo="{{ cod|e }}" data-descripcion="{{ desc|e }}">
                      <div class="d-flex justify-content-between">
                        <div class="me-2">{{ desc }}</div>
                        <span class="badge badge-code">{{ cod }}</span>
                      </div>
                    </div>
                  </div>
                {% endfor %}
              </div>
            </div>
          {% else %}
            <div class="alert alert-warning mt-3 mb-0">Sin resultados.</div>
          {% endif %}
        {% endif %}
      </div>
    </div>

    <p class="text-center text-muted mt-4 mb-0">
      Hecho para uso interno – Inventario consolidado • Ferretería El Cedro
    </p>

  </main>

  <script>
    function htmlDecode(input){const e=document.createElement('textarea');e.innerHTML=input;return e.value;}

    async function cargarDetallePorCodigo(codigo, descripcion){
      try{
        const resp=await fetch(`/detalle?codigo=${encodeURIComponent(codigo)}`);
        if(!resp.ok)throw new Error("HTTP "+resp.status);
        const data=await resp.json();
        if(data.ok){
          document.getElementById('detalle-rows').innerHTML=data.rows_html;
          document.getElementById('detalle-titulo').textContent=descripcion;
        }else{
          document.getElementById('detalle-rows').innerHTML=
            `<tr><td colspan="3" class="text-center text-danger">No hay detalle disponible</td></tr>`;
        }
      }catch(err){
        document.getElementById('detalle-rows').innerHTML=
          `<tr><td colspan="3" class="text-center text-danger">Error cargando detalle</td></tr>`;
      }
    }

    document.addEventListener('click',ev=>{
      const item=ev.target.closest('.result-item');
      if(item){
        const codigo=item.getAttribute('data-codigo');
        const descripcion=htmlDecode(item.getAttribute('data-descripcion')||codigo);
        cargarDetallePorCodigo(codigo,descripcion);
      }
    });

    document.getElementById('btn-limpiar').addEventListener('click',()=>{
      document.getElementById('detalle-rows').innerHTML=
        `<tr><td colspan="3" class="text-center text-muted">Selecciona un producto para ver el detalle por sucursal</td></tr>`;
      document.getElementById('detalle-titulo').textContent="Selecciona un producto";
    });
  </script>
</body>
</html>
"""

# -------------------- Rutas -------------------- #
@app.route("/", methods=["GET"])
def index():
    q = (request.args.get("q") or "").strip()
    results = None
    try:
        conn = get_conn()
        if q:
            results = buscar_productos(conn, q)
        conn.close()
    except Exception as e:
        results = []
        print("Error buscando:", e)

    return render_template_string(TEMPLATE, q=q, results=results)

@app.route("/detalle")
def api_detalle():
    codigo = (request.args.get("codigo") or "").strip()
    descripcion = (request.args.get("descripcion") or "").strip()
    if not codigo and not descripcion:
        abort(400, "Falta código o descripción")

    try:
        conn = get_conn()
        rows = detalle_por_producto(conn, codigo=codigo, descripcion=descripcion)
        conn.close()
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

    if not rows:
        rows_html = '<tr><td colspan="3" class="text-center text-muted">Sin detalle</td></tr>'
    else:
        rows_html = "".join(
            f"<tr><td>{html.escape(str(s))}</td><td>{html.escape(str(e))}</td><td>{html.escape(str(c))}</td></tr>"
            for s, e, c in rows
        )

    return jsonify(ok=True, rows_html=rows_html)

# -------------------- Depuración -------------------- #
@app.route("/debug_db")
def debug_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inventario';")
        exists = cur.fetchone() is not None
        count = None
        if exists:
            cur.execute("SELECT COUNT(*) FROM inventario;")
            count = cur.fetchone()[0]
        conn.close()
        return {"table_inventario": exists, "rows": count}
    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/debug_sample")
def debug_sample():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT Descripcion, Codigo FROM inventario LIMIT 10;")
        rows = cur.fetchall()
        conn.close()
        return {"sample": rows}
    except Exception as e:
        return {"error": str(e)}, 500

# -------------------- Main -------------------- #
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)


