#!/usr/bin/env python3
"""
Scraper de catálogo Masters Joyeros → masters_catalog.json
Uso: python3 scrape_masters.py
"""
import urllib.request
import re
import json
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-MX,es;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
}

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8')

def parse_price(text):
    """Extrae número de string como '12,147.00'"""
    cleaned = re.sub(r'[^\d.]', '', text.replace(',', ''))
    try:
        return float(cleaned)
    except:
        return 0.0

def parse_products(html):
    products = []
    # Divide en bloques por producto
    blocks = re.split(r'(?=<div class="porto-tb-item product)', html)

    for block in blocks[1:]:
        p = {}

        # ID del post
        m = re.search(r'post-(\d+) ', block)
        if m:
            p['id'] = m.group(1)
            p['k'] = 'MJ_' + m.group(1)

        # Nombre del producto (data-title es lo más limpio)
        m = re.search(r'data-title="([^"]+)"', block)
        if m:
            p['model'] = m.group(1).strip()

        # URL del producto
        m = re.search(r'href="(https://mastersjoyeros\.com/tienda/[^"]+)" class="img-thumbnail"', block)
        if m:
            p['url'] = m.group(1)

        # Imagen principal (primera img-responsive)
        m = re.search(r'src="(https://mastersjoyeros\.com/wp-content/uploads/[^"]+)" class="img-responsive"', block)
        if m:
            # Preferir versión 700px si existe en srcset
            srcset = re.search(r'srcset="([^"]+)"', block)
            if srcset:
                # Buscar la variante 700w
                s700 = re.search(r'(https://mastersjoyeros\.com/wp-content/uploads/\S+-700x\d+\.\w+) 700w', srcset.group(1))
                p['img'] = s700.group(1) if s700 else m.group(1)
            else:
                p['img'] = m.group(1)

        # Categorías / marca
        cats = re.findall(r'rel="tag">([^<]+)</a>', block)
        p['categories'] = cats
        # La marca es la última cat sin flechas, sin "Super Sale"
        brands = [c.strip() for c in cats if not c.startswith('→') and c.strip() not in ('Super Sale',)]
        p['brand'] = brands[-1] if brands else 'Otros'

        # Precio: si hay descuento tomamos el precio de <ins>, si no el único precio
        ins_match = re.search(
            r'<ins[^>]*>.*?<bdi>.*?>([\d,\.]+)</bdi>.*?</ins>',
            block, re.DOTALL
        )
        del_match = re.search(
            r'<del[^>]*>.*?<bdi>.*?>([\d,\.]+)</bdi>.*?</del>',
            block, re.DOTALL
        )
        plain_match = re.search(
            r'<span class="price"><span class="woocommerce-Price-amount[^"]*"><bdi>[^>]+>([\d,\.]+)</bdi>',
            block
        )

        if ins_match:
            p['price'] = parse_price(ins_match.group(1))
            p['price_original'] = parse_price(del_match.group(1)) if del_match else None
            p['on_sale'] = True
        elif plain_match:
            p['price'] = parse_price(plain_match.group(1))
            p['on_sale'] = False

        # Badge de descuento (ej: -40%)
        m = re.search(r'<div class="onsale">([^<]+)</div>', block)
        if m:
            p['sale_badge'] = m.group(1).strip()

        # Solo añadir si tiene datos mínimos
        if p.get('model') and p.get('price', 0) > 0:
            # Campos compatibles con el catálogo existente
            p['ref']       = p['id']
            p['condition'] = 'Unworn'
            p['box']       = True
            p['papers']    = True
            p['year']      = ''
            p['size']      = ''
            p['currency']  = 'MXN'
            p['source']    = 'Masters Joyeros'
            products.append(p)

    return products


all_products = []
total_pages  = 10

for page in range(1, total_pages + 1):
    url = f"https://mastersjoyeros.com/product-brand/relojes/page/{page}/?count=36"
    print(f"[{page}/{total_pages}] {url}")
    try:
        html     = fetch(url)
        products = parse_products(html)
        all_products.extend(products)
        print(f"  → {len(products)} productos encontrados")
    except Exception as e:
        print(f"  ERROR: {e}")
    time.sleep(1.5)   # pausa educada entre requests

print(f"\nTotal: {len(all_products)} productos")

with open('masters_catalog.json', 'w', encoding='utf-8') as f:
    json.dump(all_products, f, ensure_ascii=False, indent=2)

print("✓ Guardado en masters_catalog.json")
