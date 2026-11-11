"""A release switch must keep old lazy chunks accessible; uses a disposable web root."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PublishTests(unittest.TestCase):
    def test_shared_hash_assets_survive_multiple_publishes_and_failed_builds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            checkout=root/'checkout';(checkout/'deploy').mkdir(parents=True)
            script=checkout/'deploy/publish-frontend.sh';script.write_bytes((ROOT/'deploy/publish-frontend.sh').read_bytes())
            dist=checkout/'web-static/dist';(dist/'assets').mkdir(parents=True)
            web=root/'web root';legacy=web/'releases/legacy';(legacy/'assets').mkdir(parents=True)
            (legacy/'assets/old-hash.js').write_text('old')
            (web/'current').symlink_to(legacy)
            env=dict(os.environ,NOHENTAI_WEB_ROOT=str(web))
            for version in ('one','two'):
                (dist/'index.html').write_text(version)
                for asset in (dist/'assets').iterdir():asset.unlink()
                (dist/f'assets/{version}-hash.js').write_text(version)
                subprocess.run(['sh',str(script)],env=env,check=True,capture_output=True)
                self.assertEqual((web/'current/index.html').read_text(),version)
                self.assertEqual((web/'current/assets/old-hash.js').read_text(),'old')
            self.assertEqual((web/'current/assets/one-hash.js').read_text(),'one')
            current=(web/'current').resolve()
            (dist/'data').mkdir()
            self.assertNotEqual(subprocess.run(['sh',str(script)],env=env,capture_output=True).returncode,0)
            self.assertEqual((web/'current').resolve(),current)
