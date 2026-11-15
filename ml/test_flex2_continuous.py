"""Check smooth retrieval and target-run exclusion."""
import unittest
import torch
from flex2_continuous import soft_references,ContinuousCNN


class SmoothReferenceTests(unittest.TestCase):
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
