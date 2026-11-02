"""Коректне завантаження сторінок каталогу.

Правила, яких дотримується завантажувач:
  * перед першим запитом до сайту читається robots.txt, заборонені адреси не запитуються;
  * між запитами витримується пауза (за замовчуванням 2 с), кількість сторінок обмежена;
  * User-Agent чесно називає програму, без маскування під браузер;
  * якщо сайт показує перевірку «Я не робот» (Cloudflare тощо), завантаження зупиняється –
    обходити захист програма не намагається, користувачу пропонується імпорт збереженої сторінки;
  * завантажені сторінки кешуються на диску, тож повторний аналіз не створює навантаження на сайт.
"""
import hashlib
import time
import urllib.error
import urllib.request
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

USER_AGENT = 'MCO-Studio/1.0 (educational multi-criteria optimization project)'
CACHE_DIR = Path(__file__).resolve().parents[2] / 'data' / 'cache'


class ShopError(Exception):
    """Сторінку отримати не вдалося (заборона robots.txt, захист від ботів, мережа)."""


class Fetcher:
    def __init__(self, delay=2.0, cache_dir=CACHE_DIR, cache_ttl=24 * 3600, timeout=25, opener=None):
        self.delay, self.cache_dir, self.cache_ttl, self.timeout = float(delay), Path(cache_dir), cache_ttl, timeout
        self._robots = {}
        self._last = 0.0
        self._open = opener or self._urlopen          # opener(url) -> (status, text); підміняється в тестах
        self.log = []

    @staticmethod
    def _urlopen(url):
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept-Language': 'uk,en;q=0.5'})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.status, r.read().decode('utf-8', errors='replace')
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8', errors='replace')
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ShopError(f'Немає з’єднання з сайтом: {e}') from None

    def _wait(self):
        pause = self.delay - (time.monotonic() - self._last)
        if pause > 0:
            time.sleep(pause)
        self._last = time.monotonic()

    def allowed(self, url):
        host = '{0.scheme}://{0.netloc}'.format(urlparse(url))
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            self._wait()
            status, text = self._open(host + '/robots.txt')
            if status >= 500 or _is_challenge(status, text):
                raise ShopError(f'{host}: сайт не віддає robots.txt (захист від автоматичних запитів)')
            rp.parse(text.splitlines() if status == 200 else [])
            self._robots[host] = rp
        return self._robots[host].can_fetch(USER_AGENT, url)

    def get(self, url, use_cache=True):
        path = self.cache_dir / f'{urlparse(url).netloc}_{hashlib.sha1(url.encode()).hexdigest()[:16]}.html'
        if use_cache and path.exists() and time.time() - path.stat().st_mtime < self.cache_ttl:
            self.log.append(f'кеш: {url}')
            return path.read_text(encoding='utf-8')
        if not self.allowed(url):
            raise ShopError(f'Адресу {url} заборонено правилами robots.txt сайту')
        self._wait()
        status, text = self._open(url)
        if _is_challenge(status, text):
            raise ShopError('Сайт вимагає перевірки браузера (захист від ботів). Відкрийте сторінку каталогу '
                            'у браузері, збережіть її (Ctrl+S) і завантажте HTML-файл у програму.')
        if status != 200:
            raise ShopError(f'Сайт повернув код {status} для {url}')
        self.log.append(f'{status}: {url}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return text


def _is_challenge(status, text):
    head = text[:3000].lower()
    return status in (403, 429, 503) and ('just a moment' in head or 'challenge' in head or 'captcha' in head)
