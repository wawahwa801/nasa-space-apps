"""Geometry is generated from conditions and latent references without a fixed warp."""
import unittest
import torch
from flex2_geometry import GeometryHybrid,objective


class GeometryTests(unittest.TestCase):
    def test_full_resolution_rgb_mask_and_condition_gradients(self):
        torch.set_num_threads(2);torch.manual_seed(43)
        model=GeometryHybrid(3);reference=torch.rand(1,3,256,256)
        pyramid=model.encode_references(reference)
        self.assertEqual([tuple(x.shape[-2:]) for x in pyramid],[(128,128),(64,64),(32,32)])
        query=torch.rand(1,3,requires_grad=True)
        rgb,mask=model.decode(query,torch.rand(1,3),pyramid)
        self.assertEqual(tuple(rgb.shape),(1,3,256,256));self.assertEqual(tuple(mask.shape),(1,1,256,256))
        mask.mean().backward(retain_graph=True);self.assertGreater(float(query.grad.abs().sum()),0)
        loss,_=objective(rgb,mask,reference,(reference[:,:1]>.5).float())
        self.assertTrue(torch.isfinite(loss));loss.backward()

    def test_numeric_inputs_are_locally_continuous(self):
        torch.manual_seed(43);model=GeometryHybrid(3).eval()
        with torch.no_grad():
            pyramid=model.encode_references(torch.rand(1,3,256,256));q=torch.rand(1,3);r=torch.rand(1,3)
            a,ma=model.decode(q,r,pyramid);b,mb=model.decode(q+1e-4,r,pyramid)
        self.assertLess(float((a-b).abs().max()),.001)
        self.assertLess(float((ma.sigmoid()-mb.sigmoid()).abs().max()),.001)


if __name__=='__main__':unittest.main()
