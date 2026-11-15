"""A discovery shortfall must never start continuation training."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase,main
from unittest.mock import patch,MagicMock
import numpy as np

from flex2_continue import continue_run


class ContinuationTests(TestCase):
    def test_cached_matches_do_not_satisfy_new_run_count(self):
        with TemporaryDirectory() as folder:
            clock=[0.];worker=MagicMock()
            worker.wait.side_effect=lambda timeout:clock.__setitem__(0,clock[0]+timeout)
            parent=dict(epoch=5,metadata=dict(target_ids=['old']))
            with patch('flex2_continue.ORIGINAL_ROOT',Path(folder)/'data/base'),patch('flex2_continue.load_parent',return_value=parent),patch('flex2_continue.time.monotonic',side_effect=lambda:clock[0]),patch('flex2_continue.time.sleep'),patch('flex2_continue.subprocess.Popen',return_value=worker),patch('flex2_continue.prepare_all'),patch('flex2_continue.load_verified',return_value=(dict(groups=np.array(['old'])),None,None,None,None)),patch('flex2_continue.train') as training:
                with self.assertRaisesRegex(RuntimeError,'before 1 new verified runs'):
                    continue_run('parent.pt',1,.001,1,1)
                training.assert_not_called()


if __name__=='__main__':main()
