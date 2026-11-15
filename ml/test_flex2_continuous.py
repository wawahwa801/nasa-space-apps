"""Check smooth retrieval and target-run exclusion."""
import unittest
from unittest.mock import patch,MagicMock
from io import StringIO
import subprocess
import torch
from flex2_continuous import soft_references,ContinuousCNN,search_for_window


class SmoothReferenceTests(unittest.TestCase):
    def test_early_search_completion_repeats_until_full_window(self):
        clock=[0.]
        def wait(timeout):clock[0]+=5
        process=MagicMock();process.returncode=0;process.wait.side_effect=wait
        with patch('flex2_continuous.time.monotonic',side_effect=lambda:clock[0]),patch('flex2_continuous.time.sleep',side_effect=lambda seconds:clock.__setitem__(0,clock[0]+seconds)),patch('flex2_continuous.subprocess.Popen',return_value=process) as spawn:
            result=search_for_window(['worker'],StringIO(),70)
        self.assertEqual(spawn.call_count,2)
        self.assertGreaterEqual(result['elapsed_seconds'],70)

    def test_worker_is_terminated_at_deadline_before_return(self):
        clock=[0.];process=MagicMock();process.returncode=-15
        def wait(timeout):
            if clock[0]==0:
                clock[0]=timeout
                raise subprocess.TimeoutExpired('worker',timeout)
            return -15
        process.wait.side_effect=wait
        with patch('flex2_continuous.time.monotonic',side_effect=lambda:clock[0]),patch('flex2_continuous.subprocess.Popen',return_value=process):
            result=search_for_window(['worker'],StringIO(),7200)
        process.terminate.assert_called_once()
        self.assertTrue(result['passes'][0]['deadline_reached'])
        self.assertGreaterEqual(result['elapsed_seconds'],7200)

    def test_no_self_or_other_fuel_and_smooth_weights(self):
        features=torch.tensor([[0.],[.4],[.6],[1.]])
        fuels=torch.tensor([0,0,0,1]);query=torch.tensor([[.499],[.5],[.501]])
        weights=soft_references(query,features,fuels,torch.tensor([0,0,0]),torch.tensor([0,0,0]))
        self.assertTrue(torch.equal(weights[:,0],torch.zeros(3)))
        self.assertTrue(torch.equal(weights[:,3],torch.zeros(3)))
        self.assertTrue(torch.allclose(weights.sum(1),torch.ones(3)))
        self.assertLess(float((weights[0]-weights[2]).abs().max()),.01)

    def test_generator_receives_condition_gradients(self):
        torch.set_num_threads(2);torch.manual_seed(43)
        model=ContinuousCNN(3);query=torch.rand(1,3,requires_grad=True)
        image=model.decode(query,torch.rand(1,3),torch.rand(1,64,8,8))
        self.assertEqual(tuple(image.shape),(1,3,256,256))
        image.mean().backward()
        self.assertGreater(float(query.grad.abs().sum()),0)


if __name__=='__main__':unittest.main()
