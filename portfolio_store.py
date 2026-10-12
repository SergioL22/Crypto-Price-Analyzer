"""Atomic edits of the local holding snapshot (single backend process)."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid
from threading import Lock
from portfolio_view import positions

_LOCK = Lock()


class PortfolioConflict(ValueError):
    pass


class PortfolioStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else Path(__file__).resolve().parent / 'portfolio.json'

    def _read(self):
        try:
            content = self.path.read_bytes()
        except FileNotFoundError:
            content = b'{}'
        raw = json.loads(content)
        positions(raw)
        return raw, hashlib.sha256(content).hexdigest()

    @staticmethod
    def _response(raw, version):
        return {'version': version, 'holdings': positions(raw)}

    def read(self):
        with _LOCK:
            return self._response(*self._read())

    def export(self):
        """Return a CLI-compatible snapshot, including zero holdings and metadata."""
        with _LOCK:
            raw, _ = self._read()
            return json.dumps(raw, indent=2, ensure_ascii=True, allow_nan=False)

    def update(self, coin_id, amount, average, version):
        return self._change(coin_id, version, (amount, average))

    def remove(self, coin_id, version):
        return self._change(coin_id, version, None)

    @staticmethod
    def parse_backup(content):
        if len(content.encode('utf-8')) > 500_000:
            raise ValueError('Backup too large')
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('Duplicate key')
                result[key] = value
            return result
        raw = json.loads(content, object_pairs_hook=unique)
        positions(raw)
        json.dumps(raw, allow_nan=False)
        return raw

    def preview_restore(self, content):
        incoming = self.parse_backup(content)
        with _LOCK:
            current, version = self._read()
            return dict(version=version, added=sorted(incoming.keys() - current.keys()),
                        removed=sorted(current.keys() - incoming.keys()),
                        updated=sorted(key for key in current.keys() & incoming.keys() if current[key] != incoming[key]),
                        holdings=[dict(coin_id=key, amount=value['amount'], avg_buy_price=value.get('avg_buy_price', 0))
                                  for key, value in sorted(incoming.items())])

    def restore(self, content, version):
        incoming = self.parse_backup(content)
        with _LOCK:
            current, actual = self._read()
            if version != actual:
                raise PortfolioConflict('Reload before restoring.')
            # Preserve a recovery copy before replacing the complete portfolio.
            backup = self.path.with_name('portfolio-backup-' + uuid.uuid4().hex + '.json')
            with backup.open('x', encoding='utf-8') as output:
                json.dump(current, output, allow_nan=False, indent=2)
                output.flush()
                os.fsync(output.fileno())
            return self._write(incoming, version)

    def _change(self, coin_id, version, values):
        with _LOCK:
            raw, current = self._read()
            if current != version:
                raise PortfolioConflict('Reload before saving.')
            if values is None:
                if coin_id not in raw:
                    raise PortfolioConflict('Holding no longer exists.')
                del raw[coin_id]
            else:
                amount, average = values
                previous = raw.get(coin_id, {})
                raw[coin_id] = {**previous, 'symbol': previous.get('symbol', coin_id),
                                'amount': amount, 'avg_buy_price': average}
            positions(raw)
            return self._write(raw, version)

    def _write(self, raw, version):
        content = json.dumps(raw, indent=2, allow_nan=False).encode('utf-8')
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix='.portfolio-', suffix='.tmp', delete=False) as output:
                temporary = output.name
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            if self._read()[1] != version:
                raise PortfolioConflict('Reload before saving.')
            os.replace(temporary, self.path)
        finally:
            if temporary is not None and os.path.exists(temporary):
                os.unlink(temporary)
        return self._response(raw, hashlib.sha256(content).hexdigest())
