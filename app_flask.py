from flask import Flask, request, jsonify, render_template_string
import sqlite3

app = Flask(__name__)

# -----------------------------
# CONFIGURACIÓN BASE DE DATOS
# -----------------------------
DB_PATH = "inventario_el_cedro.db"

def ejecutar_query(query, params=()):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query, params)
    resultados = cursor.fetchall()
    conn.close()
    return resultados

# -----------------------------
# PLANTILLA PRINCIPAL HTML
# -----------------------------
PLANTILLA = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Ferretería El Cedro • Buscador de Inventario</title>
    <style>
        body {
            font-family: 'Segoe UI', sans-serif;
            background: #f5f8ff;
            margin: 0;
        }
        header {
            background: linear-gradient(90deg, #0a3d91, #2563eb);
            color: white;
            padding: 16px 32px;
            font-size: 22px;
            font-weight: bold;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
        .container {
            max-width: 1100px;
            margin: 40px auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            padding: 20px 30px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
        }
        th {
            background: #e8f0ff;
            color: #1e3a8a;
            text-align: left;
            padding: 10px;
            font-weight: 600;
        }
        td {
            border-bottom: 1px solid #f0f0f0;
            padding: 10px;
        }
        .search {
            display: flex;
            margin-top: 25px;
            gap: 10px;
        }
        input[type="text"] {
            flex: 1;
            padding: 10px 15px;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            font-size: 16px;
        }
        button {
            background: #1e40af;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 10px 20px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover {
            background: #2563eb;
        }
        .no-result {
            background: #fff7ed;
            color: #92400e;
            padding: 12px;
            border-radius: 6px;
            margin-top: 15px;
        }
        .footer {
            text-align: center;
            font-size: 14px;
            color: #475569;
            margin-top: 40px;
        }
    </style>
</head>
<body>
    <header>Ferretería El Cedro • Buscador de Inventario</header>

    <div class="container">
        <h3>🔹 Detalle: 
            {% if detalle %}
                {{ detalle }}
            {% else %}
                Selecciona un producto
            {% endif %}
        </h3>

        <table>
            <thead>
                <tr>
                    <th>Sucursal</th>
                    <th>Existencia</th>
                    <th>Clasificación</th>
                </tr>
            </thead>
            <tbody>
                {% if detalle_rows %}
                    {% for fila in detalle_rows %}
                        <tr>
                            <td>{{ fila[0] }}</td>
                            <td>{{ fila[1] }}</td>
                            <td>{{ fila[2] }}</td>
                        </tr>
                    {% endfor %}
                {% else %}
                    <tr><td colspan="3">Selecciona un producto para ver el detalle por sucursal</td></tr>
                {% endif %}
            </tbody>
        </table>

        <form method="get" class="search">
            <input type="text" name="q" placeholder="Buscar producto o código..." value="{{ query or '' }}">
            <button type="submit">Buscar</button>
        </form>

        {% if resultados %}
            <ul style="list-style:none; padding-left:0; margin-top:15px;">
                {% for r in resultados %}
                    <li style="padding:10px; border-bottom:1px solid #eee; cursor:pointer;"
                        onclick="seleccionarDetalle('{{ r[1]|escape }}')">
                        <strong>{{ r[1] }}</strong> — {{ r[0] }}
                    </li>
                {% endfor %}
            </ul>
        {% elif query %}
            <div class="no-result">Sin resultados.</div>
        {% endif %}
    </div>

    <div class="footer">
        Hecho para uso interno – Inventario consolidado • Ferretería El Cedro
    </div>

    <script>
        function seleccionarDetalle(nombre) {
            window.location.href = '/?detalle=' + encodeURIComponent(nombre);
        }
    </script>
</body>
</html>
"""

# -----------------------------
# RUTA PRINCIPAL
# -----------------------------
@app.route("/")
def index():
    query = request.args.get("q", "").strip()
    detalle = request.args.get("detalle", "").strip()

    resultados = []
    detalle_rows = []

    if query:
        like_param = f"%{query}%"
        resultados = ejecutar_query("""
            SELECT Codigo, Descripcion 
            FROM inventario
            WHERE Descripcion LIKE ? OR Codigo LIKE ?
            LIMIT 30
        """, (like_param, like_param))

    if detalle:
        detalle_rows = ejecutar_query("""
            SELECT Sucursal, Existencia, Clasificacion
            FROM inventario
            WHERE Descripcion = ?
        """, (detalle,))

    return render_template_string(PLANTILLA, query=query, resultados=resultados, detalle=detalle, detalle_rows=detalle_rows)


# -----------------------------
# DEBUG ENDPOINTS
# -----------------------------
@app.route("/debug_db")
def debug_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM inventario")
        rows = cursor.fetchone()[0]
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inventario'")
        table_exists = cursor.fetchone() is not None
        conn.close()
        return jsonify({"rows": rows, "table_inventario": table_exists})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/debug_sample")
def debug_sample():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM inventario LIMIT 10")
        sample = cursor.fetchall()
        conn.close()
        return jsonify({"sample": sample})
    except Exception as e:
        return jsonify({"error": str(e)})

# -----------------------------
# RENDER / LOCAL
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

