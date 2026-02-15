from dataclasses import dataclass
from queue import Empty, Queue
import threading


@dataclass
class JobResult:
    ok: bool
    value: object = None
    error: Exception | None = None
    tb: str | None = None


class BackgroundJobRunner:
    def __init__(self, root, poll_ms=40):
        self.root = root
        self.poll_ms = poll_ms
        self._queue = Queue()
        self._polling = False

    def submit(self, func, on_done, *args, on_progress=None, **kwargs):
        worker = threading.Thread(
            target=self._run_job,
            args=(func, on_done, on_progress, args, kwargs),
            daemon=True,
        )
        worker.start()
        self._ensure_polling()
        return worker

    def _run_job(self, func, on_done, on_progress, args, kwargs):
        def progress(payload):
            if callable(on_progress):
                self._queue.put(('progress', on_progress, payload))

        try:
            value = func(*args, progress=progress, **kwargs)
            result = JobResult(ok=True, value=value)
        except Exception as exc:
            result = JobResult(ok=False, error=exc, tb=traceback.format_exc())
        self._queue.put(('done', on_done, result))

    def _ensure_polling(self):
        if not self._polling:
            self._polling = True
            self.root.after(self.poll_ms, self._poll_once)

    def _poll_once(self):
        while True:
            try:
                kind, callback, payload = self._queue.get_nowait()
            except Empty:
                break
            try:
                callback(payload)
            except Exception:
                pass

        if self._polling:
            self.root.after(self.poll_ms, self._poll_once)
