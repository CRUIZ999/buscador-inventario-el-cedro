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
      --rojo: #dc2626;
      --naranja: #f97316;
    }
    *{box-sizing:border-box}
    body{margin:0;background:var(--bg);font-family:Segoe UI,system-ui,Arial,sans-serif}
    header{background:linear-gradient(90deg,var(--azul),var(--azul-2));color:#fff;padding:16px 28px;font-weight:700;font-size:20px;box-shadow:0 2px 6px rgba(0,0,0,.18)}
    .wrap{max-width:1100px;margin:32px auto;background:#fff;border-radius:12px;padding:22px 28px;box-shadow:0 6px 14px rgba(0,0,0,.08)}
    h3{margin:6px 0 14px 0;color:var(--azul)}
    table{width:100%;border-collapse:collapse;margin-top:6px}
    th{background:var(--azul-claro);color:var(--azul);text-align:left;padding:10px}
    td{padding:10px;border-bottom:1px solid #f1f5f9}
    
    .tabla-detalle th, .tabla-detalle td { text-align: center; }
    .tabla-detalle th:first-child, .tabla-detalle td:first-child { 
      text-align: left; 
      font-weight: 700;
      color: var(--azul);
    }

    /* CAMBIO 1: Se añade la clase .stock-sm para 'Sin Mov' en rojo */
    .stock-sm { color: var(--rojo); font-weight: 700; }
    .stock-c { color: var(--naranja); font-weight: 700; }

    .search{display:flex;gap:12px;margin-top:18px}
    .search input{flex:1;padding:12px 14px;border:1px solid #cbd5e1;border-radius:8px;font-size:16px}
    .btn{background:var(--azul);color:#fff;border:none;border-radius:8px;padding:12px 18px;font-size:16px;cursor:pointer}
    .btn:hover{background:var(--azul-2)}
    .item{padding:10px 6px;border-bottom:1px solid #eef2f7;cursor:pointer}
    .item b{color:#0f172a}
    .nores{background:#fff7ed;color:#92400e;padding:10px;border-radius:8px;margin-top:12px}
    .foot{margin:36px 0 6px 0;text-align:center;color:var(--gris);font-size:14px}
    .badge{color:#0f172a}
    
    .sticky-details {
      position: -webkit-sticky;
      position: sticky;
      top: 0;
      background: #fff;
      z-index: 10;
      margin-top: -22px;
      margin-left: -28px;
      margin-right: -28px;
      padding-top: 22px;
      padding-left: 28px;
      padding-right: 28px;
      padding-bottom: 12px;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
  </style>
</head>
<body>
<header>Ferretería El Cedro • Buscador de Inventario</header>

<div class="wrap">
  
  <div class="sticky-details">
    <h3 id="detalle-titulo">🔹 Detalle: Selecciona un producto</h3>

    <table class="tabla-detalle">
      <thead>
        <tr id="detalle-thead">
          <th>SUCURSALES</th>
          <th>HI</th>
          <th>EX</th>
          <th>MT</th>
          <th>SA</th>
          <th>ADE</th>
        </tr>
      </thead>
      <tbody id="detalle-tbody">
        <tr>
            <td>EXISTENCIAS</td>
            <td colspan="5">Selecciona un producto</td>
        </tr>
        <tr>
            <td>CLASIFICACION</td>
            <td colspan="5">-</td>
        </tr>
      </tbody>
    </table>
    
    <form method="get" class="search">
      <input type="text" name="q" placeholder="Buscar producto o código..." value="{{ query or '' }}">
      <button class="btn" type="submit">Buscar</button>
    </form>
    
  </div> 


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
    const titulo = document.getElementById('detalle-titulo');
    const tbody = document.getElementById('detalle-tbody');

    titulo.innerText = '🔹 Detalle: ' + nombre;
    tbody.innerHTML = `
        <tr>
            <td>EXISTENCIAS</td>
            <td colspan="5">Cargando...</td>
        </tr>
        <tr>
            <td>CLASIFICACION</td>
            <td colspan="5">-</td>
        </tr>`;

    try {
      const response = await fetch('/api/detalle?nombre=' + encodeURIComponent(nombre));
      if (!response.ok) {
        throw new Error('Error de red');
      }
      const filas = await response.json(); 

      if (filas.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td>EXISTENCIAS</td>
                <td colspan="5">No se encontraron detalles</td>
            </tr>
            <tr>
                <td>CLASIFICACION</td>
                <td colspan="5">-</td>
            </tr>`;
        return;
      }

      const datos = {};
      for (const r of filas) {
        datos[r.Sucursal] = r;
      }
      
      const sucursales = ['HI', 'EX', 'MT', 'SA', 'ADE'];

      let filaExistencias = '<td><b>EXISTENCIAS</b></td>';
      let filaClasificacion = '<td><b>CLASIFICACION</b></td>';

      for (const suc of sucursales) {
        const d = datos[suc]; 
        
        let claseColor = '';
        let clasificacionTexto = '-';
        let existenciaNum = 0; // Guardamos la existencia como número

        if (d) {
          // Obtenemos la existencia primero
          existenciaNum = parseInt(d.Existencia);
          
          if (d.Clasificacion) { 
            clasificacionTexto = d.Clasificacion.trim(); 
          }
          
          // --- CAMBIO 2: Lógica de color actualizada ---
          if (clasificacionTexto === 'C') {
            claseColor = 'stock-c'; // Naranja
          } else if (clasificacionTexto === 'Sin Mov' && existenciaNum > 0) {
            claseColor = 'stock-sm'; // Rojo
          }
          
          // --- CAMBIO 3: Abreviar "Sin Mov" ---
          if (clasificacionTexto === 'Sin Mov') {
            clasificacionTexto = 'S/M';
          }
        }
        
        // Usamos la variable 'existenciaNum' que ya es un entero
        filaExistencias += `<td class="${claseColor}">${existenciaNum}</td>`;
        // Usamos la variable 'clasificacionTexto' que puede estar abreviada
        filaClasificacion += `<td class="${claseColor}">${clasificacionTexto}</td>`;
      }

      tbody.innerHTML = `
        <tr>${filaExistencias}</tr>
        <tr>${filaClasificacion}</tr>
      `;

    } catch (error) {
      console.error('Error al cargar detalle:', error);
      tbody.innerHTML = '<tr><td colspan="6">Error al cargar los datos.</td></tr>';
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
    
    resultados = []
    
    try:
        if query:
            like_query = f"%{query}%"
            resultados = q(
                """
                SELECT Codigo, Descripcion
                FROM inventario_plain
                WHERE (Descripcion LIKE ? OR Codigo LIKE ?)
                  AND Sucursal = 'Global'
                  AND CAST(Existencia AS REAL) > 0
                LIMIT 30
                """,
                (like_query, like_query),
            )
        
        return render_template_string(
            TPL,
            query=query,
            detalle="",
            resultados=resultados,
            detalle_rows=[],
        )
    except Exception as e:
        return f"<h1>Error Crítico en la App</h1><p>{str(e)}</p>", 500


# --- ruta de API ---
@app.route("/api/detalle")
def api_detalle():
    nombre = request.args.get("nombre", "", type=str).strip()
    
    if not nombre:
        return jsonify({"error": "No se proporcionó nombre"}), 400

    detalle_rows = q(
        """
        SELECT Sucursal, Existencia, Clasificacion
        FROM inventario_plain
        WHERE Descripcion = ? AND Sucursal != 'Global'
        ORDER BY
          CASE Sucursal
            WHEN 'HI' THEN 1
            WHEN 'EX' THEN 2
            WHEN 'MT' THEN 3
            WHEN 'SA' THEN 4
            WHEN 'ADE' THEN 5
            ELSE 6
          END
        """,
        (nombre,),
    )
    
    return jsonify([dict(r) for r in detalle_rows])


# --- endpoints de depuración ---
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


# --- ejecución ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)