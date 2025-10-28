from flask import Flask, render_template_string, request, jsonify, g
import sqlite3
import os

app = Flask(__name__)
DATABASE = 'inventario.db'

# --- Configuración de Sucursales ---
SUCURSALES_ORDEN = ['HI', 'EX', 'MT', 'SA', 'ADE']

# --- Conexión a la Base de Datos ---

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row # Permite acceder a los resultados por nombre de columna
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# --- Plantilla HTML (con los cambios) ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ferretería El Cedro • Buscador de Inventario</title>
    <style>
        :root {
            --color-primario: #00529B; /* Azul oscuro */
            --color-fondo: #f4f7fa;
            --color-tarjeta: #ffffff;
            --color-texto: #333;
            --color-borde: #dde3e8;
            --color-sombra: rgba(0, 0, 0, 0.05);
            --color-cabecera: #007BFF; /* Azul brillante */
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--color-fondo);
            color: var(--color-texto);
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 20px auto;
            background-color: var(--color-tarjeta);
            border: 1px solid var(--color-borde);
            border-radius: 10px;
            box-shadow: 0 4px 12px var(--color-sombra);
            overflow: hidden;
        }
        header {
            background-color: var(--color-cabecera);
            color: white;
            padding: 20px;
            text-align: center;
        }
        header h1 {
            margin: 0;
            font-size: 1.5em;
        }
        .search-box {
            padding: 20px;
            border-bottom: 1px solid var(--color-borde);
            display: flex;
            gap: 10px;
        }
        .search-box input[type="text"] {
            flex-grow: 1;
            padding: 12px 15px;
            font-size: 1em;
            border: 1px solid var(--color-borde);
            border-radius: 6px;
        }
        .search-box button {
            padding: 12px 20px;
            font-size: 1em;
            background-color: var(--color-primario);
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        .search-box button:hover {
            background-color: #00417a;
        }
        .filters {
            padding: 10px 20px;
            background-color: #fafbfe;
            border-bottom: 1px solid var(--color-borde);
            font-size: 0.9em;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
        }
        .filters label {
            margin-right: 15px;
            display: inline-block;
            cursor: pointer;
        }
        .filters input[type="checkbox"] {
            margin-right: 5px;
        }
        .detalle-producto {
            padding: 20px;
            border-bottom: 1px solid var(--color-borde);
        }
        .detalle-producto h3 {
            margin-top: 0;
            color: var(--color-primario);
        }
        .tabla-existencias {
            width: 100%;
            border-collapse: collapse;
            text-align: center;
        }
        .tabla-existencias th, .tabla-existencias td {
            padding: 10px;
            border: 1px solid var(--color-borde);
        }
        .tabla-existencias thead {
            background-color: var(--color-fondo);
            font-size: 0.9em;
        }
        .tabla-existencias tbody td:first-child,
        .tabla-existencias tbody td:nth-child(2) { /* Ajustado si Clasificacion se muestra */
            text-align: left;
            font-weight: bold;
            font-size: 0.9em;
            vertical-align: middle;
        }
        .tabla-existencias .existencia-val {
            font-size: 1.2em;
            font-weight: bold;
        }
        .existencia-negativa {
            color: #D9534F; /* Rojo */
        }
        .search-results {
            padding: 0;
            margin: 0;
            list-style-type: none;
            max-height: 400px;
            overflow-y: auto;
        }
        .search-results li {
            padding: 15px 20px;
            border-bottom: 1px solid var(--color-borde);
            cursor: pointer;
            transition: background-color 0.2s;
        }
        .search-results li:last-child {
            border-bottom: none;
        }
        .search-results li:hover {
            background-color: #f9f9f9;
        }
        .search-results li .codigo-aq {
            font-weight: bold;
            color: var(--color-primario);
            display: block;
            font-size: 0.9em;
            margin-bottom: 3px;
        }
        .search-results li .codigo-b {
            font-weight: bold;
            color: #555;
        }
        .search-results li .desc-d {
            color: #333;
        }
        .leyenda {
            padding: 15px 20px;
            font-size: 0.8em;
            color: #777;
            background-color: var(--color-fondo);
            border-top: 1px solid var(--color-borde);
        }
        footer {
            font-size: 0.8em;
            text-align: center;
            padding: 15px;
            color: #aaa;
            background-color: #fcfcfc;
            border-top: 1px solid var(--color-borde);
        }
    </style>
</head>
<body>

    <div class="container">
        <header>
            <h1>Ferretería El Cedro • Buscador de Inventario</h1>
        </header>

        <div class="search-box">
            <input type="text" id="search-input" placeholder="Buscar por código (B, AQ) o descripción (D)..." autocomplete="off">
            <button id="search-button">Buscar</button>
        </div>

        <div class="filters">
            <div>
                <strong>Filtrar por Sucursal:</strong>
                {% for suc in SUCURSALES_ORDEN %}
                <label><input type="checkbox" name="sucursal" value="{{ suc }}"> {{ suc }}</label>
                {% endfor %}
            </div>
            <label><input type="checkbox" id="solo-con-existencia"> Solo con existencia</label>
        </div>

        <div class="detalle-producto" id="detalle-producto" style="display: none;">
            </div>
        
        <div class="leyenda" id="leyenda-clasificacion" style="display: none;">
            <strong>A:</strong> 6-12m vendidos | <strong>B:</strong> 3-5m vendidos | <strong>C:</strong> 1-2m vendidos | <strong>S/M:</strong> Sin Venta (>0)
        </div>

        <ul class="search-results" id="search-results">
            </ul>
        
        <footer id="footer-info">
            Hecho para uso interno – Inventario consolidado • Ferretería El Cedro
        </footer>
    </div>

    <script>
        // --- Variables Globales ---
        const searchInput = document.getElementById('search-input');
        const searchResults = document.getElementById('search-results');
        const detalleProducto = document.getElementById('detalle-producto');
        const leyendaClasificacion = document.getElementById('leyenda-clasificacion'); // <-- Re-agregado
        const searchButton = document.getElementById('search-button');
        const soloConExistencia = document.getElementById('solo-con-existencia');
        const sucursalCheckboxes = document.querySelectorAll('input[name="sucursal"]');
        let currentQuery = "";

        // --- Lógica de Búsqueda ---
        
        async function fetchSearch(query) {
            if (query.length < 2) {
                searchResults.innerHTML = '';
                return;
            }
            currentQuery = query;
            try {
                const response = await fetch(\`/search?q=\${encodeURIComponent(query)}\`);
                const productos = await response.json();
                displaySearchResults(productos);
            } catch (error) {
                console.error('Error en fetchSearch:', error);
                searchResults.innerHTML = '<li>Error al cargar resultados.</li>';
            }
        }

        function displaySearchResults(productos) {
            searchResults.innerHTML = '';
            if (productos.length === 0) {
                searchResults.innerHTML = '<li style="text-align: center; color: #777;">No se encontraron productos.</li>';
                return;
            }
            
            productos.forEach(producto => {
                const li = document.createElement('li');
                li.dataset.codigo = producto.Codigo;
                
                li.innerHTML = \`
                    <span class="codigo-aq">(\${producto.DescProd2 || 'S/C'})</span>
                    <span class="codigo-b">\${producto.Codigo}</span> – 
                    <span class="desc-d">\${producto.Descripcion}</span>
                \`;
                
                li.addEventListener('click', () => {
                    fetchDetalle(producto.Codigo);
                    searchResults.style.display = 'none';
                    detalleProducto.style.display = 'block';
                    leyendaClasificacion.style.display = 'block'; // <-- Re-agregado
                    searchInput.value = producto.Codigo;
                });
                searchResults.appendChild(li);
            });
        }
        
        // --- Lógica de Detalles ---
        
        async function fetchDetalle(codigo) {
            try {
                const filtros = getFiltros();
                const response = await fetch(\`/detalle?codigo=\${encodeURIComponent(codigo)}&\${filtros.query}\`);
                const data = await response.json();
                
                if (data.error) {
                    detalleProducto.innerHTML = \`<p style="color: red;">\${data.error}</p>\`;
                    return;
                }
                
                displayDetalleProducto(data, filtros.sucursales);
                
            } catch (error) {
                console.error('Error en fetchDetalle:', error);
                detalleProducto.innerHTML = '<p style="color: red;">Error al cargar el detalle del producto.</p>';
            }
        }
        
        function displayDetalleProducto(data, sucursalesFiltro) {
            const sucursalesAMostrar = sucursalesFiltro.length > 0 ? sucursalesFiltro : {{ SUCURSALES_ORDEN | tojson }};
            
            let ths = '';
            let tdsExistencia = '';
            let tdsClasificacion = ''; // <-- Re-agregado
            
            sucursalesAMostrar.forEach(suc => {
                const info = data.sucursales[suc] || { Existencia: 'N/A', Clasificacion: 'N/A' }; // <-- Re-agregado
                let existenciaNum = parseInt(info.Existencia);
                let existenciaStr = info.Existencia;
                
                let claseExistencia = '';
                if (!isNaN(existenciaNum) && existenciaNum < 0) {
                    claseExistencia = 'class="existencia-negativa"';
                }

                ths += \`<th>\${suc}</th>\`;
                tdsExistencia += \`<td \${claseExistencia}>\${existenciaStr}</td>\`;
                tdsClasificacion += \`<td>\${info.Clasificacion}</td>\`; // <-- Re-agregado
            });
            
            let stockTotal = data.global.Existencia;
            let stockTotalClase = parseInt(stockTotal) < 0 ? 'class="existencia-negativa"' : '';

            // CAMBIO: Volver a agregar la fila de Clasificación
            detalleProducto.innerHTML = \`
                <h3>Detalle: \${data.global.Descripcion}</h3>
                <p><strong>Código (B):</strong> \${data.codigo_buscado}</p>
                <p><strong>Código (AQ):</strong> \${data.global.DescProd2 || 'S/C'}</p>
                <table class="tabla-existencias">
                    <thead>
                        <tr>
                            <th></th>
                            \${ths}
                            <th>Stock Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><strong>EXISTENCIAS</strong></td>
                            \${tdsExistencia}
                            <td class="existencia-val \${stockTotalClase}">\${stockTotal}</td>
                        </tr>
                        <tr>
                            <td><strong>CLASIFICACIÓN</strong></td>
                            \${tdsClasificacion}
                            <td>\${data.global.Clasificacion}</td>
                        </tr>
                    </tbody>
                </table>
            \`;
            
            detalleProducto.style.display = 'block';
            leyendaClasificacion.style.display = 'block'; // <-- Re-agregado
        }

        // --- Lógica de Filtros ---
        
        function getFiltros() {
            const soloExistencia = soloConExistencia.checked;
            const sucursales = Array.from(sucursalCheckboxes)
                .filter(cb => cb.checked)
                .map(cb => cb.value);
            
            let queryParts = [];
            if (soloExistencia) {
                queryParts.push('solo_existencia=true');
            }
            sucursales.forEach(suc => {
                queryParts.push(\`sucursal=\${encodeURIComponent(suc)}\`);
            });
            
            return {
                query: queryParts.join('&'),
                sucursales: sucursales
            };
        }
        
        function applyFiltros() {
            const codigoActual = searchInput.value;
            if (detalleProducto.style.display === 'block' && codigoActual) {
                fetchDetalle(codigoActual);
            }
        }
        
        // --- Event Listeners ---
        
        let searchTimeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            if (e.target.value === '') {
                searchResults.innerHTML = '';
                detalleProducto.style.display = 'none';
                leyendaClasificacion.style.display = 'none'; // <-- Re-agregado
                searchResults.style.display = 'block';
                return;
            }
            
            if (searchResults.style.display === 'none') {
                searchResults.style.display = 'block';
                detalleProducto.style.display = 'none';
                leyendaClasificacion.style.display = 'none'; // <-- Re-agregado
            }
            
            searchTimeout = setTimeout(() => {
                fetchSearch(e.target.value);
            }, 300);
        });

        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                clearTimeout(searchTimeout);
                fetchSearch(searchInput.value);
            }
        });
        
        searchButton.addEventListener('click', () => {
            clearTimeout(searchTimeout);
            fetchSearch(searchInput.value);
        });

        soloConExistencia.addEventListener('change', applyFiltros);
        sucursalCheckboxes.forEach(cb => {
            cb.addEventListener('change', applyFiltros);
        });

    </script>
</body>
</html>
"""

# --- Rutas de la Aplicación ---

@app.route('/')
def index():
    if not os.path.exists(DATABASE):
        return "Error: La base de datos 'inventario.db' no se ha construido. Ejecuta 'build_index.py' primero.", 500
    
    return render_template_string(HTML_TEMPLATE, SUCURSALES_ORDEN=SUCURSALES_ORDEN)

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    query_fts = f'"{query}"*' 
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT DescProd2, Codigo, Descripcion FROM inventario WHERE inventario MATCH ? ORDER BY rank LIMIT 50",
            (query_fts,)
        )
        productos = [dict(row) for row in cur.fetchall()]
        return jsonify(productos)
        
    except sqlite3.Error as e:
        print(f"Error de búsqueda SQLite: {e}")
        return jsonify({"error": "Error en la base de datos"}), 500

@app.route('/detalle')
def detalle():
    codigo = request.args.get('codigo', '').strip()
    if not codigo:
        return jsonify({"error": "No se proporcionó código de producto"}), 400

    solo_existencia = request.args.get('solo_existencia') == 'true'
    sucursales_filtro = request.args.getlist('sucursal')

    try:
        conn = get_db()
        cur = conn.cursor()
        
        # CAMBIO: Volver a agregar 'Clasificacion'
        query_sql = "SELECT Sucursal, Existencia, Clasificacion, DescProd2, Descripcion FROM inventario_plain WHERE Codigo = ?"
        params = [codigo]
        
        if solo_existencia:
            query_sql += " AND Sucursal != 'Global' AND CAST(Existencia AS INTEGER) > 0"
        
        if sucursales_filtro:
            placeholders = ', '.join('?' for _ in sucursales_filtro)
            query_sql += f" AND Sucursal IN ({placeholders})"
            params.extend(sucursales_filtro)

        cur.execute(query_sql, params)
        resultados = cur.fetchall()
        
        if not resultados:
            cur.execute("SELECT 1 FROM inventario_plain WHERE Codigo = ? LIMIT 1", (codigo,))
            if not cur.fetchone():
                return jsonify({"error": "Código de producto no encontrado"}), 404
            else:
                return jsonify({"error": "No se encontraron existencias con los filtros aplicados"}), 404

        data = {
            "codigo_buscado": codigo,
            "sucursales": {},
            "global": {}
        }
        
        # CAMBIO: Volver a agregar 'Clasificacion'
        cur.execute("SELECT Existencia, Clasificacion, DescProd2, Descripcion FROM inventario_plain WHERE Codigo = ? AND Sucursal = 'Global'", (codigo,))
        global_data = cur.fetchone()
        
        if global_data:
            data['global'] = dict(global_data)

        for row in resultados:
            if row['Sucursal'] != 'Global':
                data['sucursales'][row['Sucursal']] = dict(row)

        return jsonify(data)

    except sqlite3.Error as e:
        print(f"Error de detalle SQLite: {e}")
        return jsonify({"error": "Error en la base de datos"}), 500

if __name__ == "__main__":
    if not os.path.exists(DATABASE):
        print(f"Error: No se encuentra la base de datos '{DATABASE}'.")
        print("Por favor, ejecuta 'python build_index.py' primero para crearla.")
    else:
        app.run(debug=True)