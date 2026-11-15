"""Check continuous mask/texture composition without nearest-reference switches."""
import unittest
import torch
from flex2_texture import texture_composite,mask_moments


class TextureTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)
        y,x=torch.meshgrid(torch.linspace(-1,1,64),torch.linspace(-1,1,64),indexing='ij');radius=(x*x+y*y).sqrt()
        self.masks=torch.stack([(radius<.4).float(),(radius<.65).float()])[:,None]
        self.images=self.masks.repeat(1,3,1,1)*torch.tensor([.3,.2,.9])[None,:,None,None]
        self.geometry=(8*(.5-radius)).sigmoid()[None,None]

    def test_small_weight_changes_produce_small_pixel_changes(self):
        a,ma=texture_composite(self.geometry,self.images,self.masks,torch.tensor([.5,.5]))
        b,mb=texture_composite(self.geometry,self.images,self.masks,torch.tensor([.5001,.4999]))
        self.assertTrue(torch.isfinite(a).all());self.assertLess(float((a-b).abs().max()),.001)
        self.assertLess(float((ma-mb).abs().max()),.001)
        self.assertGreater(float(a.max()),.1)

    def test_geometry_changes_transported_visual_support(self):
        _,a=texture_composite(self.geometry,self.images,self.masks,torch.tensor([.5,.5]))
        bigger=torch.nn.functional.interpolate(self.geometry,size=96,mode='bilinear',align_corners=False)[:,:,16:80,16:80]
        _,b=texture_composite(bigger,self.images,self.masks,torch.tensor([.5,.5]))
        self.assertGreater(float(b.sum()),float(a.sum()))

    def test_empty_mask_moments_remain_finite(self):
        mean,cov=mask_moments(torch.zeros(1,1,64,64))
        self.assertTrue(torch.isfinite(mean).all());self.assertTrue(torch.isfinite(cov).all())

    def test_more_geometry_influence_moves_shape_toward_cnn(self):
        shifted=torch.roll(self.geometry,10,dims=-1)
        _,a=texture_composite(shifted,self.images,self.masks,torch.tensor([.5,.5]),geometry_share=.2)
        _,b=texture_composite(shifted,self.images,self.masks,torch.tensor([.5,.5]),geometry_share=.9)
        center_a,_=mask_moments(a);center_b,_=mask_moments(b)
        self.assertGreater(float(center_b[0,0]),float(center_a[0,0]))

    def test_invalid_geometry_and_concentration_are_rejected(self):
        for share,concentration in [(1.1,2),(.8,0),(.8,5)]:
            with self.assertRaises(ValueError):
                texture_composite(self.geometry,self.images,self.masks,torch.tensor([.5,.5]),share,concentration)


if __name__=='__main__':unittest.main()
