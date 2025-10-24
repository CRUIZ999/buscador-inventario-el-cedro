
from flask import Flask, render_template_string, request, jsonify
import sqlite3

app = Flask(__name__)

TEMPLATE = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Ferretería El Cedro • Buscador de Inventario</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body{ background:#f7f7f7; }
    .mono{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono","Courier New", monospace;}
    .result-item{ cursor:pointer; }
    .result-item:hover{ background:#f1f5f9; }
  </style>
</head>
<body>
  <nav class="navbar navbar-dark bg-success mb-4">
    <div class="container-fluid">
      <span class="navbar-brand mb-0 h1">Ferretería El Cedro • Buscador de Inventario</span>
    </div>
  </nav>

  <div class="container mb-5">

    <!-- 1) TABLA DE DETALLE ARRIBA -->
    <div class="card shadow-sm mb-4">
      <div class="card-header bg-light">
        <strong id="detalle-titulo">Detalle: <span class="text-muted">selecciona un producto</span></strong>
      </div>
      <div class="card-body p-0">
        <div class="table-responsive">
          <table class="table table-sm mb-0">
            <thead class="table-success">
              <tr>
                <th style="width:35%">Sucursal</th>
                <th style="width:25%">Existencia</th>
                <th style="width:40%">Clasificación</th>
              </tr>
            </thead>
            <tbody id="detalle-body">
              <tr class="text-muted">
                <td colspan="3" class="py-3 text-center">Selecciona un producto para ver el detalle por sucursal</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="card-footer text-end">
        <button class="btn btn-outline-secondary btn-sm" id="btn-limpiar" type="button">Limpiar detalle</button>
      </div>
    </div>

    <!-- 2) BUSCADOR + RESULTADOS ABAJO -->
    <div class="card shadow-sm">
      <div class="card-body">
        <form id="form-buscar" method="get" class="mb-3">
          <div class="input-group">
            <input name="q" id="q" type="text" class="form-control" placeholder="Buscar producto o código..." value="{{ q or '' }}" autocomplete="off">
            <button class="btn btn-success" type="submit">Buscar</button>
          </div>
          <div class="form-text">Tip: puedes teclear varios términos (ej. <code>taladro 1/2 truper</code>)</div>
        </form>

        {% if results is not none %}
          {% if results %}
            <div class="alert alert-success py-2">Resultados encontrados: {{ results|length }}</div>
            <div class="list-group shadow-sm">
              {% for r in results %}
                <!-- Cada renglón es clickeable -->
                <div
                  class="list-group-item d-flex align-items-center justify-content-between result-item"
                  data-codigo="{{ r['Codigo'] }}"
                  data-descripcion="{{ r['Descripcion'] }}"
                  tabindex="0"
                  title="Click para ver detalle"
                >
                  <div>
                    <div class="fw-semibold">{{ r["Descripcion"] }}</div>
                    <div class="text-muted small mono">{{ r["Codigo"] }}</div>
                  </div>
                </div>
              {% endfor %}
            </div>
          {% else %}
            <div class="alert alert-warning mb-0">Sin resultados.</div>
          {% endif %}
        {% endif %}
      </div>
    </div>

    <div class="text-center mt-4 text-muted">
      Hecho para uso interno – Inventario consolidado • Ferretería El Cedro
    </div>
  </div>

  <script>
    // Carga el detalle vía API y pinta la tabla superior
    async function cargarDetallePorCodigo(codigo, descripcion){
      const titulo = document.getElementById('detalle-titulo');
      const cuerpo = document.getElementById('detalle-body');
      titulo.innerHTML = 'Detalle: <span class="text-success">' + (descripcion || codigo) + '</span>';
      cuerpo.innerHTML = '<tr><td colspan="3" class="py-3 text-center text-muted">Cargando...</td></tr>';

      try{
        const resp = await fetch('/api/detalle?codigo=' + encodeURIComponent(codigo));
        if(!resp.ok){ throw new Error('Error HTTP ' + resp.status); }
        const data = await resp.json();

        if(!data.ok || data.rows.length === 0){
          cuerpo.innerHTML = '<tr><td colspan="3" class="py-3 text-center text-muted">Sin datos para este producto.</td></tr>';
          return;
        }

        let html = '';
        for(const row of data.rows){
          html += '<tr>'
               +   '<td>' + row.Sucursal + '</td>'
               +   '<td>' + row.Existencia + '</td>'
               +   '<td>' + (row.Clasificacion || '') + '</td>'
               + '</tr>';
        }
        cuerpo.innerHTML = html;

        // Subir a la tabla
        window.scrollTo({ top: 0, behavior: 'smooth' });

      }catch(err){
        console.error(err);
        cuerpo.innerHTML = '<tr><td colspan="3" class="py-3 text-center text-danger">Ocurrió un error cargando el detalle.</td></tr>';
      }
    }

    // Click en cualquier renglón de resultado
    document.addEventListener('click', function(ev){
      const row = ev.target.closest('.result-item');
      if(row){
        const codigo = row.getAttribute('data-codigo');
        const descripcion = row.getAttribute('data-descripcion');
        cargarDetallePorCodigo(codigo, descripcion);
      }
    });

    // (Opcional) Enter/Espacio para accesibilidad
    document.addEventListener('keydown', function(ev){
      const row = ev.target.closest('.result-item');
      if(row && (ev.key === 'Enter' || ev.key === ' ')){
        ev.preventDefault();
        const codigo = row.getAttribute('data-codigo');
        const descripcion = row.getAttribute('data-descripcion');
        cargarDetallePorCodigo(codigo, descripcion);
      }
    });

    // Limpiar tabla
    document.getElementById('btn-limpiar').addEventListener('click', function(){
      document.getElementById('detalle-titulo').innerHTML =
        'Detalle: <span class="text-muted">selecciona un producto</span>';
      document.getElementById('detalle-body').innerHTML =
        '<tr class="text-muted"><td colspan="3" class="py-3 text-center">Selecciona un producto para ver el detalle por sucursal</td></tr>';
    });

    // Si llegó con ?auto=CODIGO, cargar automáticamente
    {% if auto_codigo and auto_desc %}
      cargarDetallePorCodigo("{{ auto_codigo }}", "{{ auto_desc|e }}");
    {% endif %}
  </script>
</body>
</html>
"""

def _db():
    return sqlite3.connect("inventario_el_cedro.db")

@app.route("/", methods=["GET"])
def index():
    q = (request.args.get("q") or "").strip()
    results = None
    auto_codigo = None
    auto_desc = None

    if q:
        tokens = [t for t in q.split() if t]
        like = "%" + "%".join(tokens) + "%" if tokens else "%"
        conn = _db()
        cur = conn.cursor()
        cur.execute("""
            SELECT Codigo, Descripcion
            FROM inventario
            WHERE Descripcion LIKE ? OR Codigo LIKE ?
            GROUP BY Codigo, Descripcion
            ORDER BY Descripcion
            LIMIT 100;
        """, (like, like))
        rows = cur.fetchall()
        conn.close()
        results = [{"Codigo": r[0], "Descripcion": r[1]} for r in rows]

        auto_codigo = request.args.get("codigo")
        auto_desc   = request.args.get("detalle")

    return render_template_string(
        TEMPLATE,
        q=q,
        results=results,
        auto_codigo=auto_codigo,
        auto_desc=auto_desc
    )

@app.route("/api/detalle", methods=["GET"])
def api_detalle():
    codigo = (request.args.get("codigo") or "").strip()
    if not codigo:
        return jsonify(ok=False, error="Falta 'codigo'"), 400

    conn = _db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT Sucursal,
               SUM(Existencia) AS Existencia,
               MAX(Clasificacion) AS Clasificacion
        FROM inventario
        WHERE Codigo = ?
        GROUP BY Sucursal
        ORDER BY Sucursal;
    """, (codigo,))
    rows = cur.fetchall()
    conn.close()

    data = [
        {"Sucursal": r[0], "Existencia": float(r[1]) if r[1] is not None else 0.0, "Clasificacion": r[2]}
        for r in rows
    ]
    return jsonify(ok=True, rows=data)

if __name__ == "__main__":
  app.run(host="0.0.0.0", port=8000, debug=False)
