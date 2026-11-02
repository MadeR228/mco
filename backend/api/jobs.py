"""Фонові задачі: завантаження каталогу магазину і побудова фронту NSGA-II тривають секунди,
тому запит одразу повертає id задачі, а клієнт опитує її стан з прогресом."""
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from mco.shops import ShopError

TTL = 3600            # скільки секунд зберігати завершені задачі
MAX_JOBS = 200


class JobStore:
    def __init__(self, workers=2):
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='mco-job')
        self._jobs = {}
        self._lock = threading.Lock()

    def submit(self, kind, fn):
        """fn(report) виконується у фоні; report(частка 0..1, повідомлення) оновлює прогрес."""
        self._cleanup()
        job_id = uuid.uuid4().hex
        job = {'id': job_id, 'kind': kind, 'status': 'queued', 'progress': 0.0, 'message': '',
               'result': None, 'error': None, 'created': time.time(), 'finished': None}
        with self._lock:
            self._jobs[job_id] = job

        def report(fraction, message=''):
            with self._lock:
                job['progress'] = round(min(max(float(fraction), 0.0), 1.0), 4)
                if message:
                    job['message'] = message

        def run():
            with self._lock:
                job['status'] = 'running'
            try:
                result = fn(report)
                with self._lock:
                    job.update(status='done', progress=1.0, result=result)
            except (ValueError, ShopError) as e:
                with self._lock:
                    job.update(status='error', error=str(e))
            except Exception as e:      # непередбачена помилка не повинна «вбити» робочий потік
                with self._lock:
                    job.update(status='error', error=f'Внутрішня помилка: {type(e).__name__}')
            finally:
                with self._lock:
                    job['finished'] = time.time()

        self._pool.submit(run)
        return self.get(job_id)

    def get(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            return None if job is None else {k: v for k, v in job.items() if k not in ('created', 'finished')}

    def _cleanup(self):
        now = time.time()
        with self._lock:
            old = [k for k, j in self._jobs.items() if j['finished'] and now - j['finished'] > TTL]
            for k in old:
                del self._jobs[k]
            if len(self._jobs) > MAX_JOBS:
                done = sorted((j['finished'], k) for k, j in self._jobs.items() if j['finished'])
                for _, k in done[:len(self._jobs) - MAX_JOBS]:
                    del self._jobs[k]


jobs = JobStore()
