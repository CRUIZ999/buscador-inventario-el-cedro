# ------------------ rutas ------------------
@app.route("/")
def home():
    query = request.args.get("q", "", type=str).strip()
    filtro_stock = request.args.get("filtro_stock")
    is_checked = (filtro_stock == "on") # True si el checkbox está marcado
    
    resultados = []
    
    try:
        if query:
            like_query = f"%{query}%"
            
            # --- CORRECCIÓN AQUÍ ---
            # Movemos el filtro CAST(...) > 0 para que siempre se aplique
            # cuando is_checked es True.
            sql = """
                SELECT Codigo, Descripcion, Existencia
                FROM inventario_plain
                WHERE (Descripcion LIKE ? OR Codigo LIKE ?)
                  AND Sucursal = 'Global'
            """
            
            params = [like_query, like_query] 
            
            # Añadir el filtro de stock SOLO si el checkbox está marcado
            if is_checked: 
                # Usamos CAST( AS REAL) para convertir texto a número antes de comparar
                sql += " AND CAST(Existencia AS REAL) > 0" 
            
            sql += " LIMIT 30"
            
            resultados_raw = q(sql, tuple(params)) 

            # Aplicar resaltado
            resultados = []
            for r in resultados_raw:
                res_dict = dict(r) 
                # Convertimos Existencia a entero aquí para mostrarlo bien
                # (aunque el filtro ya usó la versión REAL/decimal)
                try:
                    res_dict['Existencia'] = int(float(res_dict['Existencia']))
                except (ValueError, TypeError):
                    res_dict['Existencia'] = 0 # O algún valor por defecto si no es número
                
                res_dict['HighlightedDesc'] = highlight_term(res_dict['Descripcion'], query)
                resultados.append(res_dict)

        return render_template_string(
            TPL,
            query=query,
            detalle="",
            resultados=resultados,
            detalle_rows=[],
            filtro_stock_checked=is_checked # Pasar el estado del checkbox
        )
    except Exception as e:
        print(f"Error en la ruta home: {e}") 
        return f"<h1>Error Crítico en la App</h1><p>{str(e)}</p>", 500