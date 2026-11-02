"""Розпізнавання характеристик ноутбука з текстового опису картки товару.

Інтернет-магазини показують характеристики короткими рядками різного формату:
  Rozetka:  '15.6" IPS / AMD Ryzen 7 7840HS / RAM 16 ГБ / SSD 512 ГБ / RTX 3050, 6 ГБ'
  Brain:    '16", 2560x1600, Intel Core 5 210H (2.2 - 4.8 ГГц), DDR - 16 ГБ, SSD - 512 ГБ, 60 Втг, 2.49 кг'
  Telemart: 'Дисплей: 15.6″ (1920x1080, IPS) Процесор: Intel Core 5 315 … Вага: 1.7 кг'
Функція parse_specs() витягує з таких рядків числові критерії, а cpu_score() оцінює
продуктивність процесора за довідковою таблицею (умовні бали багатопотокового тесту,
та сама шкала, що й у data/laptops.csv).
"""
import re

NUM = r'(\d+(?:[.,]\d+)?)'

# Орієнтовні бали багатопотокової продуктивності (шкала Geekbench 6 Multi-Core).
CPU_SCORES = {
    # Intel Celeron / Pentium / N-серія
    'celeron n4020': 750, 'celeron n4120': 1100, 'celeron n4500': 900, 'celeron n5100': 1500,
    'pentium n5030': 1300, 'pentium n6000': 1700, 'n100': 2800, 'n150': 3000, 'n200': 3000, 'i3-n305': 4700,
    # Intel Core 11–14 покоління
    'i3-1115g4': 2900, 'i3-1215u': 5500, 'i3-1305u': 5600, 'i3-1315u': 5800, 'i3-1220p': 6300,
    'i5-1135g7': 4800, 'i5-1155g7': 5100, 'i5-1235u': 7000, 'i5-1240p': 8300, 'i5-1334u': 7200,
    'i5-1335u': 7500, 'i5-1340p': 9000, 'i5-11400h': 6800, 'i5-12450h': 8500, 'i5-12500h': 10000,
    'i5-13420h': 9500, 'i5-13450hx': 12000, 'i5-13500h': 11000, 'i5-14450hx': 12500, 'i5-13500hx': 13500,
    'i7-1165g7': 5300, 'i7-1255u': 7800, 'i7-1260p': 9000, 'i7-1355u': 8200, 'i7-1360p': 10000,
    'i7-11800h': 8500, 'i7-12650h': 11000, 'i7-12700h': 12000, 'i7-13620h': 12500, 'i7-13700h': 13000,
    'i7-13650hx': 15000, 'i7-13700hx': 16000, 'i7-14650hx': 16500, 'i7-14700hx': 17000,
    'i9-12900h': 13000, 'i9-13900h': 14000, 'i9-13900hx': 17500, 'i9-13980hx': 18000, 'i9-14900hx': 18500,
    # Intel Core 3/5/7 (Series 1–2) і Core Ultra
    'core 3 100u': 6000, 'core 5 120u': 8000, 'core 5 210h': 10000, 'core 5 220h': 11000,
    'core 3 304': 5000, 'core 5 315': 7000, 'core 5 320': 7500,
    'core 7 150u': 8800, 'core 7 240h': 12500, 'core 7 250h': 13000,
    'ultra 5 115u': 7500, 'ultra 5 125u': 8500, 'ultra 5 125h': 11000, 'ultra 5 135u': 9000,
    'ultra 5 135h': 11500, 'ultra 5 225u': 9000, 'ultra 5 225h': 12500, 'ultra 5 226v': 9500,
    'ultra 5 228v': 9700, 'ultra 7 155u': 9000, 'ultra 7 155h': 12500, 'ultra 7 165h': 13000,
    'ultra 7 165u': 9300, 'ultra 7 255u': 10000, 'ultra 7 255h': 14500, 'ultra 7 256v': 10800,
    'ultra 7 258v': 11000, 'ultra 7 268v': 11200, 'ultra 9 185h': 13500, 'ultra 9 275hx': 20000,
    'ultra 9 285h': 15500, 'ultra 9 288v': 11500, 'ultra 7 356h': 15000, 'ultra 9 290hx': 21000,
    # AMD Ryzen
    'ryzen 3 30': 4000, 'ryzen 5 40': 5500, 'ryzen 5 150': 8500, 'ryzen 7 170': 10000,
    'ryzen 7 7445hs': 9000, 'ryzen 7 8745hs': 11000, 'ryzen 7 h255': 11500, 'ryzen 9 8940hx': 16500,
    'ryzen 3 5300u': 4300, 'ryzen 3 7320u': 3800, 'ryzen 3 7330u': 5000, 'ryzen 3 7335u': 5200,
    'ryzen 5 5500u': 5500, 'ryzen 5 5600h': 6500, 'ryzen 5 5625u': 6200, 'ryzen 5 6600h': 7300,
    'ryzen 5 7430u': 6600, 'ryzen 5 7520u': 4100, 'ryzen 5 7530u': 6800, 'ryzen 5 7535hs': 8000,
    'ryzen 5 7535u': 7300, 'ryzen 5 7235hs': 7300, 'ryzen 5 7640hs': 10500, 'ryzen 5 7540u': 8500,
    'ryzen 5 8540u': 8600, 'ryzen 5 8640hs': 10500, 'ryzen 5 8645hs': 10600, 'ryzen 5 220': 10000,
    'ryzen 5 230': 10300, 'ryzen 5 240': 10500,
    'ryzen 7 5700u': 6200, 'ryzen 7 5800h': 7400, 'ryzen 7 5825u': 6900, 'ryzen 7 6800h': 9000,
    'ryzen 7 7730u': 7200, 'ryzen 7 7735hs': 9500, 'ryzen 7 7435hs': 8800, 'ryzen 7 7840hs': 11500,
    'ryzen 7 7840u': 10500, 'ryzen 7 8840hs': 11800, 'ryzen 7 8845hs': 12000, 'ryzen 7 8840u': 10800,
    'ryzen 7 250': 11800, 'ryzen 7 260': 12000,
    'ryzen 9 7940hs': 12500, 'ryzen 9 7945hx': 17000, 'ryzen 9 8945hs': 12800, 'ryzen 9 270': 12800,
    'ryzen ai 5 340': 10500, 'ryzen ai 7 350': 13000, 'ryzen ai 9 365': 14000, 'ryzen ai 9 hx 370': 15000,
    'ryzen ai 9 hx 375': 15200, 'ryzen ai max+ 395': 20000,
    # Apple і Qualcomm
    'apple m1': 8300, 'apple m2': 9700, 'apple m3': 11800, 'apple m3 pro': 15000, 'apple m4': 14800,
    'apple m4 pro': 22500, 'apple m4 max': 25500, 'apple m5': 17000, 'apple a18 pro': 8500,
    'nvidia grace': 18000, 'snapdragon x plus': 13000, 'snapdragon x elite': 14500, 'snapdragon x': 11000,
}

# Наближена оцінка, якщо моделі немає в таблиці: базовий рівень сімейства × коефіцієнт суфікса
FAMILY_BASE = [
    (r'celeron', 1000), (r'pentium', 1800), (r'\bn\d{3}\b', 2800), (r'ryzen ai 9', 14500), (r'ryzen ai 7', 13000),
    (r'ryzen ai 5', 10500), (r'ultra 9', 14000), (r'ultra 7', 11000), (r'ultra 5', 9000), (r'i9-', 14000),
    (r'i7-', 10000), (r'i5-', 8000), (r'i3-', 5500), (r'core 7 ', 10000), (r'core 5 ', 8500), (r'core 3 ', 6000),
    (r'ryzen 9', 12500), (r'ryzen 7', 9500), (r'ryzen 5', 7000), (r'ryzen 3', 4500), (r'apple m', 12000),
    (r'snapdragon', 12000), (r'mediatek|athlon', 2000),
]
SUFFIX = [(r'\d+hx\b', 1.45), (r'\d+h[sx]?\b', 1.15), (r'\d+p\b', 1.05), (r'\d+u\b', 0.9), (r'\d+g\d\b', 0.75)]

CPU_PATTERNS = [
    r'apple\s+(?:m\d(?:\s+(?:pro|max))?|a\d{2}\s+pro)',
    r'snapdragon\s+x(?:\s+(?:plus|elite))?', r'ryzen\s+ai\s+(?:max\+?\s+)?\d\s+(?:hx\s+)?\d{3}',
    r'ryzen\s+\d\s+h?\d{2,4}[a-z]{0,2}\b', r'nvidia\s+grace', r'core\s+ultra\s+\d\s+\d{3}[a-z]{0,2}\b',
    r'core\s+i\d[\s-]+\d{4,5}[a-z]{0,2}\d?\b', r'i\d-n?\d{3,5}[a-z]{0,2}\d?\b', r'core\s+[357]\s+\d{3}[a-z]?\b',
    r'celeron\s+n?\d{4}', r'pentium\s+(?:silver\s+|gold\s+)?n?\d{4}', r'\bn(?:100|150|200|250|300)\b',
    r'\ba1[78]\s+pro\b', r'mediatek\s+\w+', r'athlon\s+\w+\s*\d*',
]


def _num(s):
    return float(s.replace(',', '.'))


def find_cpu(text):
    """Назва процесора з тексту картки (рядок у нижньому регістрі) або None."""
    t = ' '.join(text.lower().replace('™', '').replace('®', '').split())
    if 'macbook' in t:          # у назвах MacBook чип вказано без слова Apple: «MacBook Air 13" M4 16/512GB»
        m = re.search(r'\b(m[1-5](?:\s+(?:pro|max))?|a1[78]\s+pro)\b', t)
        if m:
            return 'apple ' + m.group(1)
    for p in CPU_PATTERNS:
        m = re.search(p, t)
        if m:
            return re.sub(r'core\s+i(\d)[\s-]+', r'core i\1-', m.group(0).strip())   # «Core i9 14900HX» → «i9-14900HX»
    return None


def _cpu_key(cpu):
    c = cpu.lower().replace('intel ', '').replace('amd ', '').replace('qualcomm ', '')
    c = re.sub(r'core\s+i(\d)[\s-]+', r'i\1-', c)
    c = re.sub(r'core\s+ultra\s+', 'ultra ', c)
    c = c.replace('pentium silver ', 'pentium ').replace('pentium gold ', 'pentium ')
    return ' '.join(c.split())


def cpu_score(cpu):
    """(бали, джерело): 'таблиця' – точне значення з довідника, 'оцінка' – наближене, None – невідомо."""
    if not cpu:
        return None, None
    key = _cpu_key(cpu)
    if key in CPU_SCORES:
        return CPU_SCORES[key], 'таблиця'
    for k in sorted(CPU_SCORES, key=len, reverse=True):     # «apple m4 pro» раніше за «apple m4»
        if key.startswith(k):
            return CPU_SCORES[k], 'таблиця'
    for pat, base in FAMILY_BASE:
        if re.search(pat, key):
            mult = next((m for s, m in SUFFIX if re.search(s, key)), 1.0)
            return int(round(base * mult, -2)), 'оцінка'
    return None, None


def parse_specs(text):
    """Словник характеристик, знайдених у тексті (відсутні ключі – не знайдено)."""
    t = text.replace('&quot;', '"').replace('″', '"').replace('”', '"').replace('\xa0', ' ')
    out = {}
    m = re.search(NUM + r'\s*(?:"|дюйм)', t)
    if m and 10 <= _num(m.group(1)) <= 19:
        out['screen'] = _num(m.group(1))
    m = (re.search(r'RAM\s*' + NUM + r'\s*(?:ГБ|GB)', t, re.I)
         or re.search(r'DDR\d?\w*\s*-\s*' + NUM + r'\s*ГБ', t)
         or re.search(r'Оперативна пам.ять:\s*' + NUM + r'\s*ГБ', t)
         or re.search(r'\b(\d{1,2})\s*/\s*\d{3,4}\s*(?:GB|ГБ)', t))
    if m:
        out['ram'] = _num(m.group(1))
    m = (re.search(r'SSD\s*-?\s*' + NUM + r'\s*(ГБ|ТБ|GB|TB)', t, re.I)
         or re.search(NUM + r'\s*(ГБ|ТБ|GB|TB)\s*\(?\s*SSD', t, re.I)
         or re.search(r'\b\d{1,2}\s*/\s*(\d{3,4}|[12])\s*(GB|ГБ|TB|ТБ)', t))
    if m:
        v = _num(m.group(1))
        out['ssd'] = v * 1024 if m.group(2).upper() in ('ТБ', 'TB') or v <= 4 else v
    m = re.search(r'\b(RTX\s*\d{4}(?:\s*Ti)?|GTX\s*\d{4}(?:\s*Ti)?|RX\s*\d{4}[A-Z]{0,2}|Arc\s+A\d{3}M)', t, re.I)
    out['dgpu'] = 1 if m else 0
    if m:
        out['gpu'] = ' '.join(m.group(1).split()).upper().replace('TI', 'Ti')
        v = (re.search(re.escape(m.group(1)) + r'[^/]{0,12}?,\s*' + NUM + r'\s*ГБ', t)
             or re.search(r'GPU\s*-\s*' + NUM + r'\s*ГБ', t))
        if v:
            out['vram'] = _num(v.group(1))
    m = re.search(NUM + r'\s*(?:Втг|Вт·год|Вт\*год|Вт-год|Wh)', t, re.I)
    if m:
        out['battery_wh'] = _num(m.group(1))
    m = re.search(r'(?<![\d.])(\d(?:[.,]\d{1,3})?)\s*кг', t)
    if m and 0.5 <= _num(m.group(1)) <= 5:
        out['weight'] = _num(m.group(1))
    m = re.search(r'(\d{2,3})\s*Гц', t)
    if m:
        out['hz'] = float(m.group(1))
    cpu = find_cpu(t)
    if cpu:
        out['cpu'] = cpu
        out['cpu_score'], out['cpu_source'] = cpu_score(cpu)
    return out


def pretty_cpu(cpu):
    """«core i5-13420h» → «Core i5-13420H», «ryzen ai 9 hx 370» → «Ryzen AI 9 HX 370»."""
    words = []
    for w in (cpu or '').split():
        if re.fullmatch(r'i\d-\w+', w):
            words.append(w[:3] + w[3:].upper())
        elif any(ch.isdigit() for ch in w) or w in ('ai', 'hx', 'x'):
            words.append(w.upper())
        else:
            words.append(w.capitalize())
    return ' '.join(words)


def parse_price(text):
    """«29 999₴» → 29999.0."""
    digits = re.sub(r'[^\d]', '', str(text))
    return float(digits) if digits else None
