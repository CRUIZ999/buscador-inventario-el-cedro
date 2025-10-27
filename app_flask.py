from flask import Flask, request, jsonify, render_template_string
import sqlite3
import html
import re # Necesario para el resaltado
import os

app = Flask(__name__)

DB_PATH = "inventario_el_cedro.db"


# ------------------ utilidades DB ------------------
def q(query, params=()):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # print("--- SQL DEBUG ---") # Descomentar para depurar
        # print("SQL:", query)
        # print("Params:", params)
        # print("-----------------")
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error en la base de datos: {e}")
        print(f"SQL Fallido: {query}")
        print(f"Params Fallidos: {params}")
        return []

# --- Función para resaltar ---
def highlight_term(text, term):
    if not term: return text
    try:
        return re.sub(f'({re.escape(term)})', r'<mark>\1</mark>', text, flags=re.IGNORECASE)
    except re.error: return text


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
      --gris:#475569; --bg:#f5f8ff; --gris-claro: #f1f5f9;
      --rojo: #dc2626; --naranja: #f97316; --amarillo-resaltar: #fef08a;
    }
    *{box-sizing:border-box}
    body{margin:0;background:var(--bg);font-family:Segoe UI,system-ui,Arial,sans-serif}
    header{ background:linear-gradient(90deg,var(--azul),var(--azul-2)); color:#fff; height: 60px; padding: 0 28px; display: flex; align-items: center; font-weight:700; font-size:20px; box-shadow:0 2px 6px rgba(0,0,0,.18); position: sticky; top: 0; z-index: 20; }
    .wrap{max-width:1100px;margin:32px auto;background:#fff;border-radius:12px;padding:22px 28px;box-shadow:0 6px 14px rgba(0,0,0,.08)}
    h3{margin:6px 0 14px 0;color:var(--azul)}
    table{width:100%;border-collapse:collapse;margin-top:6px}
    th{background:var(--azul-claro);color:var(--azul);text-align:left;padding:10px}
    td{padding:10px;border-bottom:1px solid var(--gris-claro)}
    .tabla-detalle th, .tabla-detalle td { text-align: center; }
    .tabla-detalle th:first-child, .tabla-detalle td:first-child { text-align: left; font-weight: 700; color: var(--azul); }
    .stock-sm { color: var(--rojo); font-weight: 700; }
    .stock-c { color: var(--naranja); font-weight: 700; }

    .search-container { position: relative; flex: 1; }
    .search { display:flex; gap:12px; margin-top:18px; }
    .search input{ flex:1; padding:12px 14px; border:1px solid #cbd5e1; border-radius:8px; font-size:16px; padding-right: 35px; }
    .clear-search { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; font-size: 20px; color: var(--gris); cursor: pointer; padding: 0 5px; display: none; }
    .search input:not(:placeholder-shown) + .clear-search { display: block; }

    .btn{background:var(--azul);color:#fff;border:none;border-radius:8px;padding:12px 18px;font-size:16px;cursor:pointer}
    .btn:hover{background:var(--azul-2)}
    .btn:disabled{background:var(--gris);cursor:not-allowed}

    .item{ display: flex; justify-content: space-between; align-items: center; padding: 12px 8px; border-bottom: 1px solid #eef2f7; cursor: pointer; }
    .item-desc { flex-grow: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-right: 10px;}
    .item-desc b{color:#0f172a}
    .item-desc .badge{color:#0f172a}
    .item-desc mark { background-color: var(--amarillo-resaltar); padding: 0 2px; border-radius: 3px; color: #1e293b; }
    .stock-badge { flex-shrink: 0; font-weight: 700; color: var(--azul); padding-left: 15px; }
    .item:nth-child(even) { background-color: #f8faff; }
    .item:hover { background-color: var(--azul-claro); }

    .filters-container { display: flex; justify-content: space-between; align-items: flex-end; gap: 20px; margin-top: 15px; padding-bottom: 15px; border-bottom: 1px solid var(--gris-claro); flex-wrap: wrap;}
    .filter-group { display: flex; flex-direction: column; gap: 5px; }
    .filter-group label { font-weight: 600; color: var(--azul); margin-bottom: 3px; font-size: 14px;}
    /* Se elimina el estilo select ya que no hay */
    .sucursal-filters { display: flex; gap: 15px; align-items: center; flex-wrap: wrap; }
    .sucursal-filters label { font-weight: normal; color: var(--gris); margin: 0; font-size: 14px; cursor: pointer;}
    .sucursal-filters input { margin-right: 4px; vertical-align: middle; cursor: pointer;}

    .filter-box { margin-top: 12px; text-align: right; color: var(--gris); /* Ajustar margen si es necesario */ flex-grow: 1; /* Ocupar espacio sobrante */}
    .filter-box input { margin-right: 6px; vertical-align: middle; }
    .filter-box label { vertical-align: middle; cursor: pointer; }

    .nores{background:#fff7ed;color:#92400e;padding:10px;border-radius:8px;margin-top:12px}
    .foot{margin:36px 0 6px 0;text-align:center;color:var(--gris);font-size:14px}
    .sticky-details { position: sticky; top: 60px; background: #fff; z-index: 10; margin: -22px -28px 0 -28px; padding: 22px 28px 12px 28px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }
    .spinner { border: 4px solid rgba(0, 0, 0, 0.1); width: 36px; height: 36px; border-radius: 50%; border-left-color: var(--azul); animation: spin 1s ease infinite; margin: 10px auto; }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
  </style>
</head>
<body>
<header>Ferretería El Cedro • Buscador de Inventario</header>
<div class="wrap">
  <div class="sticky-details">
    <h3 id="detalle-titulo">🔹 Detalle: Selecciona un producto</h3>
    <table class="tabla-detalle">
      <thead><tr id="detalle-thead"><th>SUCURSALES</th><th>HI</th><th>EX</th><th>MT</th><th>SA</th><th>ADE</th></tr></thead>
      <tbody id="detalle-tbody"><tr><td>EXISTENCIAS</td><td colspan="5">Selecciona un producto</td></tr><tr><td>CLASIFICACION</td><td colspan="5">-</td></tr></tbody>
    </table>
    <form method="get" class="search" id="search-form">
      <div class="search-container">
        <input type="text" name="q" placeholder="Buscar producto o código..." value="{{ query or '' }}" id="search-input">
        <button type="button" class="clear-search" onclick="clearSearch()" title="Limpiar búsqueda">&times;</button>
      </div>
      <button class="btn" type="submit" id="search-button">Buscar</button>
      {# #}
      {% for suc in SUCURSALES_DISPONIBLES %}<input type="hidden" name="sucursal_{{ suc }}" value="on" {% if suc not in sucursales_seleccionadas %}disabled{% endif %}>{% endfor %}
      {# #}
      <input type="hidden" name="filtro_stock" value="on" {% if not filtro_stock_checked %}disabled{% endif %}>
    </form>
    <div class="filters-container">
      <div class="filter-group">
        <label>Filtrar por Sucursal:</label>
        <div class="sucursal-filters">
          {% for suc in SUCURSALES_DISPONIBLES %}
          <label><input type="checkbox" name="sucursal" value="{{ suc }}" form="search-form" onchange="submitFormOnChange()" {% if suc in sucursales_seleccionadas %}checked{% endif %}> {{ suc }}</label>
          {% endfor %}
        </div>
      </div>
      {# #}
      {# #}
      <div class="filter-box">
        <input type="checkbox" name="filtro_stock" value="on" id="filtro_stock" form="search-form" onchange="submitFormOnChange()" {% if filtro_stock_checked %}checked{% endif %}>
        <label for="filtro_stock">Solo con existencia</label>
      </div>
    </div>
  </div>
  {% if resultados %}
    <div style="margin-top:10px">
      {% for r in resultados %}
        <div class="item" onclick="sel('{{ r['Descripcion']|e }}')">
          <div class="item-desc"><b>{{ r['HighlightedDesc']|safe }}</b> <span class="badge">— {{ r['Codigo'] }}</span></div>
          <span class="stock-badge">Stock: {{ r['Existencia'] | int }}</span>
        </div>
      {% endfor %}
    </div>
  {% elif query %}
    <div class="nores">Sin resultados para "{{ query }}" con los filtros aplicados.</div>
  {% else %}
     <div class="nores" style="text-align:center;">Ingresa un término de búsqueda.</div>
  {% endif %}
</div>
<div class="foot">Hecho para uso interno – Inventario consolidado • Ferretería El Cedro</div>
<script>
  async function sel(nombre) { /* ... (código sel() sin cambios) ... */
    const titulo = document.getElementById('detalle-titulo');
    const tbody = document.getElementById('detalle-tbody');
    titulo.innerText = '🔹 Detalle: ' + nombre;
    tbody.innerHTML = `<tr><td colspan="6"><div class="spinner"></div></td></tr>`;
    try {
      const response = await fetch('/api/detalle?nombre=' + encodeURIComponent(nombre));
      if (!response.ok) throw new Error('Error de red');
      const filas = await response.json();
      if (filas.length === 0) {
        tbody.innerHTML = `<tr><td>EXISTENCIAS</td><td colspan="5">No se encontraron detalles</td></tr><tr><td>CLASIFICACION</td><td colspan="5">-</td></tr>`;
        return;
      }
      const datos = {};
      filas.forEach(r => datos[r.Sucursal] = r);
      const sucursales = ['HI', 'EX', 'MT', 'SA', 'ADE'];
      let filaExistencias = '<td><b>EXISTENCIAS</b></td>';
      let filaClasificacion = '<td><b>CLASIFICACION</b></td>';
      sucursales.forEach(suc => {
        const d = datos[suc];
        let claseColor = '', clasificacionTexto = '-', existenciaNum = 0;
        if (d) {
          existenciaNum = parseInt(d.Existencia);
          if (d.Clasificacion) clasificacionTexto = d.Clasificacion.trim();
          if (clasificacionTexto === 'C') claseColor = 'stock-c';
          else if (clasificacionTexto === 'Sin Mov' && existenciaNum > 0) claseColor = 'stock-sm';
          if (clasificacionTexto === 'Sin Mov') clasificacionTexto = 'S/M';
        }
        filaExistencias += `<td class="${claseColor}">${existenciaNum}</td>`;
        filaClasificacion += `<td class="${claseColor}">${clasificacionTexto}</td>`;
      });
      tbody.innerHTML = `<tr>${filaExistencias}</tr><tr>${filaClasificacion}</tr>`;
    } catch (error) {
      console.error('Error al cargar detalle:', error);
      tbody.innerHTML = '<tr><td colspan="6">Error al cargar los datos.</td></tr>';
    }
  }

  const searchForm = document.getElementById('search-form');
  const searchButton = document.getElementById('search-button');
  if (searchForm) {
    searchForm.addEventListener('submit', function() {
      if (document.querySelector('input[name="q"]').value) {
        searchButton.disabled = true; searchButton.innerText = 'Buscando...';
      }
      Array.from(searchForm.querySelectorAll('input[type=hidden][disabled]')).forEach(el => el.parentNode.removeChild(el));
    });
  }
  function clearSearch() {
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
      searchInput.value = '';
      Array.from(searchForm.querySelectorAll('input[type=hidden]')).forEach(el => el.disabled = false);
      Array.from(searchForm.querySelectorAll('input[name=sucursal]')).forEach(el => el.checked = false);
      // Se elimina la línea de orden
      document.getElementById('filtro_stock').checked = true;
      searchForm.submit();
    }
  }
  function submitFormOnChange() {
      Array.from(searchForm.querySelectorAll('input[type=hidden][disabled]')).forEach(el => el.parentNode.removeChild(el));
      searchForm.submit();
  }
</script>
</body>
</html>
"""

# ------------------ Constantes ------------------
SUCURSALES_DISPONIBLES = ['HI', 'EX', 'MT', 'SA', 'ADE']

# ------------------ rutas ------------------
@app.route("/")
def home():
    query = request.args.get("q", "", type=str).strip()
    filtro_stock = request.args.get("filtro_stock")
    is_checked = (filtro_stock == "on")
    
    sucursales_seleccionadas = request.args.getlist("sucursal") 
    # Se elimina orden_seleccionado
    
    apply_sucursal_filter = bool(sucursales_seleccionadas) 
    sucursales_for_query = sucursales_seleccionadas if apply_sucursal_filter else SUCURSALES_DISPONIBLES
        
    resultados = []
    
    try:
        if query:
            like_query = f"%{query}%"
            params = [like_query, like_query] 
            
            # --- CORRECCIÓN FINAL (v7): Lógica SQL sin Ordenación ---
            
            sql_select = "SELECT DISTINCT p_global.Codigo, p_global.Descripcion, p_global.Existencia\n"
            sql_from = "FROM inventario_plain p_global\n"
            sql_join = ""
            sql_where = "WHERE p_global.Sucursal = 'Global'\n  AND (p_global.Descripcion LIKE ? OR p_global.Codigo LIKE ?)\n"
            
            where_conditions = []
            
            if apply_sucursal_filter:
                if not sql_join: sql_join = "JOIN inventario_plain p_sucursal ON p_global.Codigo = p_sucursal.Codigo\n"
                placeholders = ', '.join('?' * len(sucursales_for_query))
                where_conditions.append(f"p_sucursal.Sucursal IN ({placeholders})")
                params.extend(sucursales_for_query)
            
            if is_checked:
                if not sql_join: sql_join = "JOIN inventario_plain p_sucursal ON p_global.Codigo = p_sucursal.Codigo\n"
                where_conditions.append("CAST(p_sucursal.Existencia AS REAL) > 0")
                where_conditions.append("p_sucursal.Sucursal != 'Global'")

            if where_conditions:
                sql_where += "  AND " + "\n  AND ".join(where_conditions)

            # Se elimina la cláusula ORDER BY
            sql = sql_select + sql_from + sql_join + sql_where + " LIMIT 30"
            
            final_params = [like_query, like_query] + params[2:]
            
            resultados_raw = q(sql, tuple(final_params)) 

            resultados = []
            for r in resultados_raw:
                res_dict = dict(r) 
                try: res_dict['Existencia'] = int(float(res_dict['Existencia']))
                except (ValueError, TypeError): res_dict['Existencia'] = 0 
                res_dict['HighlightedDesc'] = highlight_term(res_dict['Descripcion'], query)
                resultados.append(res_dict)

        displayed_sucursales = sucursales_seleccionadas if apply_sucursal_filter else []

        return render_template_string(
            TPL,
            query=query, detalle="", resultados=resultados, detalle_rows=[],
            filtro_stock_checked=is_checked,
            SUCURSALES_DISPONIBLES=SUCURSALES_DISPONIBLES,
            sucursales_seleccionadas=displayed_sucursales, 
            # Se elimina orden_seleccionado
        )
    except Exception as e:
        print(f"Error en la ruta home: {e}") 
        try:
             displayed_sucursales_on_error = sucursales_seleccionadas if apply_sucursal_filter else []
             return render_template_string(
                TPL, query=query, detalle="", resultados=[], detalle_rows=[],
                filtro_stock_checked=is_checked, SUCURSALES_DISPONIBLES=SUCURSALES_DISPONIBLES,
                sucursales_seleccionadas=displayed_sucursales_on_error,
                # Se elimina orden_seleccionado
                error_message=f"Error al buscar: {str(e)}"
            )
        except: 
            return f"<h1>Error Crítico en la App</h1><p>{str(e)}</p>", 500


# --- ruta de API ---
@app.route("/api/detalle")
def api_detalle():
    nombre = request.args.get("nombre", "", type=str).strip()
    if not nombre: return jsonify({"error": "No se proporcionó nombre"}), 400
    detalle_rows = q(
        """SELECT Sucursal, Existencia, Clasificacion FROM inventario_plain WHERE Descripcion = ? AND Sucursal != 'Global'
           ORDER BY CASE Sucursal WHEN 'HI' THEN 1 WHEN 'EX' THEN 2 WHEN 'MT' THEN 3 WHEN 'SA' THEN 4 WHEN 'ADE' THEN 5 ELSE 6 END""",
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
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/debug_sample")
def debug_sample():
    try:
        sample = q("SELECT Codigo, Descripcion, Existencia, Clasificacion, Sucursal FROM inventario_plain LIMIT 10")
        return jsonify({"sample": [dict(r) for r in sample]})
    except Exception as e: return jsonify({"error": str(e)}), 500


# --- ejecución ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)