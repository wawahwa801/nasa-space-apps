"""Structure and continuity checks for the aligned hybrid."""
import unittest
import numpy as np
import torch
from flex2_shape import ShapeHybrid,aligned_data


class ShapeTests(unittest.TestCase):
    def test_initial_model_preserves_reference_and_has_continuous_input_path(self):
        torch.set_num_threads(2);model=ShapeHybrid(3)
        reference=torch.rand(1,3,256,256)*.8+.1
        query=torch.rand(1,3);rgb,mask,flow=model(query,query,reference)
        self.assertLess(float((rgb-reference).abs().max().detach()),1e-4)
        self.assertEqual(tuple(mask.shape),(1,1,256,256));self.assertEqual(tuple(flow.shape),(1,2,256,256))
        rgb.mean().backward();self.assertIsNotNone(model.conv[-1].weight.grad)

    def test_alignment_applies_identical_translation_to_weak_mask(self):
        images=np.zeros((1,256,256,3),dtype=np.uint8);images[0,40:100,20:80,2]=180
        masks=np.zeros((1,256,256),dtype=np.float32);masks[0,40:100,20:80]=1
        aligned,shifted=aligned_data(images,masks)
        self.assertTrue(np.array_equal(aligned[0,:,:,2]>0,shifted[0]>0))


if __name__=='__main__':unittest.main()
