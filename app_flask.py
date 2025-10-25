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

    .stock-d { color: var(--rojo); font-weight: 700; }
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