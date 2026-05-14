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

def extract_price(block):
    """Intenta múltiples patrones para extraer precio."""
    # 1) Precio con descuento: <ins>
    ins_match = re.search(
        r'<ins[^>]*>.*?<bdi[^>]*>.*?>([\d,\.]+)</bdi>.*?</ins>',
        block, re.DOTALL
    )
    del_match = re.search(
        r'<del[^>]*>.*?<bdi[^>]*>.*?>([\d,\.]+)</bdi>.*?</del>',
        block, re.DOTALL
    )
    if ins_match:
        return (
            parse_price(ins_match.group(1)),
            parse_price(del_match.group(1)) if del_match else None,
            True
        )

    # 2) Precio normal en woocommerce-Price-amount
    m = re.search(
        r'woocommerce-Price-amount[^>]*>.*?<bdi[^>]*>[^<]*<[^>]+>([\d,\.]+)</bdi>',
        block, re.DOTALL
    )
    if m:
        return parse_price(m.group(1)), None, False

    # 3) Cualquier <bdi> con número después de símbolo de moneda
    m = re.search(r'<bdi>\s*(?:<[^>]+>)?(?:\$|MXN|&#36;|&\#36;)?\s*?([\d,\.]+)\s*</bdi>', block)
    if m:
        return parse_price(m.group(1)), None, False

    # 4) Buscar cualquier número que parezca precio (4+ dígitos con coma/punto)
    prices = re.findall(r'(?:\$|MXN)\s*([\d]{1,3}(?:,[\d]{3})*(?:\.[\d]{2})?)', block)
    if prices:
        return parse_price(prices[0]), None, False

    return 0.0, None, False


def parse_products(html):
    products = []
    skipped_no_price = 0

    # Divide en bloques por producto
    blocks = re.split(r'(?=<div[^>]+class="[^"]*porto-tb-item[^"]*product)', html)

    for block in blocks[1:]:
        p = {}

        # ID del post
        m = re.search(r'post-(\d+)\b', block)
        if m:
            p['id'] = m.group(1)
            p['k'] = 'MJ_' + m.group(1)

        # Nombre del producto
        m = re.search(r'data-title="([^"]+)"', block)
        if not m:
            # Fallback: título en el enlace de producto
            m = re.search(r'class="woocommerce-loop-product__title">([^<]+)<', block)
        if m:
            p['model'] = m.group(1).strip()

        # URL del producto
        m = re.search(r'href="(https://mastersjoyeros\.com/tienda/[^"]+)"', block)
        if m:
            p['url'] = m.group(1)

        # Imagen principal
        m = re.search(r'src="(https://mastersjoyeros\.com/wp-content/uploads/[^"]+?)"', block)
        if m:
            srcset = re.search(r'srcset="([^"]+)"', block)
            if srcset:
                s700 = re.search(
                    r'(https://mastersjoyeros\.com/wp-content/uploads/\S+-700x\d+\.\w+) 700w',
                    srcset.group(1)
                )
                p['img'] = s700.group(1) if s700 else m.group(1)
            else:
                p['img'] = m.group(1)

        # Categorías / marca
        cats = re.findall(r'rel="tag">([^<]+)</a>', block)
        p['categories'] = cats
        brands = [c.strip() for c in cats if not c.startswith('→') and c.strip() not in ('Super Sale',)]
        p['brand'] = brands[-1] if brands else 'Otros'

        # Precio
        price, price_orig, on_sale = extract_price(block)
        p['price'] = price
        p['price_original'] = price_orig
        p['on_sale'] = on_sale

        # Badge de descuento
        m = re.search(r'<div class="onsale">([^<]+)</div>', block)
        if m:
            p['sale_badge'] = m.group(1).strip()

        # Solo añadir si tiene nombre
        if p.get('model'):
            if p['price'] == 0:
                skipped_no_price += 1

            p['ref']       = p.get('id', '')
            p['condition'] = 'Unworn'
            p['box']       = True
            p['papers']    = True
            p['year']      = ''
            p['size']      = ''
            p['currency']  = 'MXN'
            p['source']    = 'Masters Joyeros'
            products.append(p)

    return products, skipped_no_price


all_products = []
total_pages  = 10

for page in range(1, total_pages + 1):
    url = f"https://mastersjoyeros.com/product-brand/relojes/page/{page}/?count=36"
    print(f"[{page}/{total_pages}] {url}")
    try:
        html = fetch(url)
        products, skipped = parse_products(html)
        all_products.extend(products)
        print(f"  → {len(products)} productos ({skipped} sin precio)")
    except Exception as e:
        print(f"  ERROR: {e}")
    time.sleep(1.5)

print(f"\nTotal: {len(all_products)} productos")
with_price = [p for p in all_products if p['price'] > 0]
print(f"Con precio: {len(with_price)}")
print(f"Sin precio: {len(all_products) - len(with_price)}")

with open('masters_catalog.json', 'w', encoding='utf-8') as f:
    json.dump(all_products, f, ensure_ascii=False, indent=2)

print("✓ Guardado en masters_catalog.json")
