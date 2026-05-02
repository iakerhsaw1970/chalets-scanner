import os
import json
import feedparser
import requests
from datetime import datetime

API_KEY = os.environ.get("OPENROUTER_API_KEY")

FEEDS = [
    "https://www.pisos.com/rss/chalet/compra/espana/",
    "https://www.milanuncios.com/rss/inmobiliaria/chalets-en-venta.htm",
]

FILTROS = {
    "precio_max": 160000,
    "superficie_min": 90,
}

def obtener_anuncios():
    anuncios = []
    for url in FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                anuncios.append({
                    "titulo": entry.get("title", "Sin título"),
                    "url": entry.get("link", ""),
                    "descripcion": entry.get("summary", ""),
                    "fecha": entry.get("published", ""),
                })
        except Exception as e:
            print(f"Error feed {url}: {e}")
    return anuncios

def analizar_con_ia(anuncios):
    prompt = f"""Eres un experto en análisis inmobiliario en España.
Analiza estos anuncios de chalets y devuelve SOLO un JSON válido con esta estructura:
{{
  "anuncios": [
    {{
      "titulo": "...",
      "precio": 0,
      "superficie": 0,
      "precio_m2": 0,
      "ubicacion": "...",
      "url": "...",
      "score": 0,
      "clasificacion": "chollo|interesante|normal|descartado",
      "motivo": "...",
      "fecha": "..."
    }}
  ],
  "resumen": {{
    "total": 0,
    "nuevos": 0,
    "descartados": 0,
    "tendencia": "subida|estable|bajada"
  }}
}}

Filtros obligatorios:
- Precio máximo: 160.000€
- Superficie mínima: 90m²
- Jardín privado obligatorio
- Suministros de red (luz, agua, alcantarillado)
- Estado habitable, reforma máxima 10.000€
- Descartar: ocupadas, subasta, sin fotos, info incompleta

Scoring 0-100:
- 40% precio vs mercado (€/m²)
- 25% características
- 20% ubicación
- 15% calidad anuncio

Anuncios a analizar:
{json.dumps(anuncios, ensure_ascii=False)}
"""

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "meta-llama/llama-3.3-70b-instruct:free",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4000,
        }
    )

    texto = response.json()["choices"][0]["message"]["content"]
    texto = texto.replace("```json", "").replace("```", "").strip()
    return json.loads(texto)

def generar_html(datos):
    anuncios = datos.get("anuncios", [])
    resumen = datos.get("resumen", {})
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")

    tops = [a for a in anuncios if a["clasificacion"] in ["chollo", "interesante"]][:5]
    cholloss = [a for a in anuncios if a["clasificacion"] == "chollo"]

    def clase_score(s):
        if s >= 75: return "s-high"
        if s >= 50: return "s-mid"
        return "s-low"

    def pill(c):
        if c == "chollo": return '<span class="pill pill-green2">🟢🟢 Chollo</span>'
        if c == "interesante": return '<span class="pill pill-green">🟢 Interesante</span>'
        if c == "normal": return '<span class="pill pill-yellow">🟡 Normal</span>'
        return '<span class="pill pill-red">🔴 Descartado</span>'

    cards_html = ""
    for i, a in enumerate(tops, 1):
        es_chollo = a["clasificacion"] == "chollo"
        cards_html += f"""
        <div class="top-card {'chollo' if es_chollo else ''}">
          <div class="card-header">
            <div>
              <div class="card-rank {'chollo-tag' if es_chollo else ''}">{'🟢🟢 Chollo · ' if es_chollo else '🟢 Interesante · '}#{i}</div>
              <div class="card-title">{a['titulo']}</div>
            </div>
            <div class="score-circle {'high' if a['score']>=75 else 'mid'}">{a['score']}</div>
          </div>
          <div class="card-body">
            <div class="price-row">
              <div class="price-main">{a['precio']:,} €</div>
              <div class="price-sqm">{a['precio_m2']} €/m²</div>
            </div>
            <div class="card-reason"><strong>Motivo:</strong> {a['motivo']}</div>
            <div class="card-footer">
              <div class="location">📍 {a['ubicacion']}</div>
              <a class="btn-ver" href="{a['url']}" target="_blank">VER →</a>
            </div>
          </div>
        </div>"""

    filas_html = ""
    for a in anuncios:
        filas_html += f"""
        <tr>
          <td class="td-title">{a['titulo']}</td>
          <td class="td-price">{a['precio']:,} €</td>
          <td class="td-sqm">{a['precio_m2']} €/m²</td>
          <td class="td-sqm">{a['superficie']} m²</td>
          <td class="td-sqm">{a['ubicacion']}</td>
          <td class="td-score {clase_score(a['score'])}">{a['score']}</td>
          <td>{pill(a['clasificacion'])}</td>
          <td class="td-date">{a['fecha']}</td>
          <td><a class="btn-ver" href="{a['url']}" target="_blank">→</a></td>
        </tr>"""

    alerta_html = ""
    if cholloss:
        c = cholloss[0]
        alerta_html = f"""
        <div class="alert-chollo">
          <div class="alert-icon">🟢🟢</div>
          <div class="alert-content">
            <div class="alert-head">CHOLLO DETECTADO — PRIORIDAD MÁXIMA</div>
            <p><strong>{c['titulo']}</strong> · {c['precio']:,} € · Score: <strong>{c['score']}/100</strong><br>{c['motivo']}</p>
          </div>
        </div>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>InmoScanner · Informe Diario</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0b0f14;--surface:#111820;--surface2:#162030;--border:#1e2e40;--accent:#00d4a8;--accent2:#f5a623;--red:#ff4a4a;--yellow:#f5c842;--green:#22c98e;--green2:#00ff9d;--text:#e8edf3;--muted:#6b8299;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--bg);color:var(--text);font-family:'Outfit',sans-serif;font-size:14px;line-height:1.6;}}
header{{background:linear-gradient(135deg,#0b0f14 0%,#0f1e2e 50%,#091a2a 100%);border-bottom:1px solid var(--border);padding:32px 48px 28px;}}
.logo{{font-family:'DM Serif Display',serif;font-size:28px;color:var(--text);}} .logo span{{color:var(--accent);}}
.badge-date{{font-family:'DM Mono',monospace;font-size:11px;color:var(--accent);background:rgba(0,212,168,0.08);border:1px solid rgba(0,212,168,0.25);padding:4px 10px;border-radius:4px;}}
.container{{max-width:1100px;margin:0 auto;padding:40px 32px;}}
.stats-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin-bottom:40px;}}
.stat-card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:18px 20px;}}
.stat-label{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px;font-family:'DM Mono',monospace;}}
.stat-value{{font-size:28px;font-weight:700;color:var(--text);}}
.top-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px;margin-bottom:40px;}}
.top-card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden;}}
.top-card.chollo{{border-color:var(--green2);background:linear-gradient(160deg,#0d2318 0%,var(--surface) 60%);}}
.card-header{{padding:16px 18px 12px;border-bottom:1px solid var(--border);display:flex;align-items:flex-start;justify-content:space-between;gap:10px;}}
.card-rank{{font-family:'DM Mono',monospace;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;}}
.card-rank.chollo-tag{{color:var(--green2);background:rgba(0,255,157,0.08);border:1px solid rgba(0,255,157,0.25);padding:2px 8px;border-radius:20px;}}
.card-title{{font-size:14px;font-weight:600;color:var(--text);line-height:1.4;margin-top:4px;}}
.score-circle{{width:44px;height:44px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-family:'DM Mono',monospace;font-size:13px;font-weight:500;flex-shrink:0;border:2px solid;}}
.score-circle.high{{color:var(--green2);border-color:rgba(0,255,157,0.4);background:rgba(0,255,157,0.06);}}
.score-circle.mid{{color:var(--yellow);border-color:rgba(245,200,66,0.4);background:rgba(245,200,66,0.06);}}
.card-body{{padding:14px 18px;}}
.price-row{{display:flex;align-items:baseline;gap:10px;margin-bottom:10px;}}
.price-main{{font-family:'DM Serif Display',serif;font-size:22px;color:var(--text);}}
.price-sqm{{font-family:'DM Mono',monospace;font-size:11px;color:var(--muted);background:var(--surface2);padding:2px 7px;border-radius:4px;}}
.card-reason{{font-size:12px;color:var(--muted);background:var(--surface2);border-left:3px solid var(--accent);padding:8px 12px;border-radius:0 6px 6px 0;margin-bottom:12px;}}
.card-reason strong{{color:var(--accent);}}
.card-footer{{display:flex;align-items:center;justify-content:space-between;padding-top:10px;border-top:1px solid var(--border);}}
.location{{font-size:12px;color:var(--muted);}}
.btn-ver{{font-size:11px;color:var(--accent);text-decoration:none;border:1px solid rgba(0,212,168,0.3);padding:4px 12px;border-radius:5px;font-family:'DM Mono',monospace;}}
.table-wrap{{overflow-x:auto;border:1px solid var(--border);border-radius:10px;margin-bottom:40px;}}
table{{width:100%;border-collapse:collapse;font-size:13px;}}
thead{{background:var(--surface2);border-bottom:1px solid var(--border);}}
th{{padding:12px 14px;text-align:left;font-family:'DM Mono',monospace;font-size:10px;text-transform:uppercase;letter-spacing:0.8px;color:var(--muted);}}
td{{padding:12px 14px;border-top:1px solid var(--border);vertical-align:middle;}}
.td-title{{font-weight:500;color:var(--text);max-width:220px;}}
.td-price{{font-family:'DM Mono',monospace;font-weight:500;}}
.td-sqm{{font-family:'DM Mono',monospace;color:var(--muted);font-size:12px;}}
.td-score{{font-family:'DM Mono',monospace;font-weight:600;}}
.td-date{{font-family:'DM Mono',monospace;color:var(--muted);font-size:11px;}}
.s-high{{color:var(--green2);}} .s-mid{{color:var(--yellow);}} .s-low{{color:var(--red);}}
.pill{{display:inline-block;padding:2px 9px;border-radius:20px;font-size:11px;font-weight:500;}}
.pill-green{{background:rgba(0,255,157,0.1);color:var(--green2);border:1px solid rgba(0,255,157,0.2);}}
.pill-green2{{background:rgba(0,255,157,0.2);color:#00ffaa;border:1px solid rgba(0,255,157,0.4);font-weight:700;}}
.pill-yellow{{background:rgba(245,200,66,0.1);color:var(--yellow);border:1px solid rgba(245,200,66,0.2);}}
.pill-red{{background:rgba(255,74,74,0.1);color:var(--red);border:1px solid rgba(255,74,74,0.2);}}
.alert-chollo{{background:linear-gradient(135deg,rgba(0,255,157,0.06) 0%,rgba(0,212,168,0.02) 100%);border:1px solid rgba(0
