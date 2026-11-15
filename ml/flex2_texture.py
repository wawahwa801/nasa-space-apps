"""Experimental continuous renderer: learned geometry with recorded RGB detail.

This renderer does not train a new model or establish physical accuracy.
"""
import torch
import torch.nn.functional as F


def mask_moments(mask):
    """Continuous centroid/covariance in normalized image coordinates."""
    n,_,h,w=mask.shape
    yy,xx=torch.meshgrid(torch.linspace(-1,1,h,device=mask.device),torch.linspace(-1,1,w,device=mask.device),indexing='ij')
    coordinates=torch.stack([xx,yy],-1).reshape(-1,2)
    probability=mask.flatten(1).clamp(min=0)+1e-8
    probability=probability/probability.sum(1,keepdim=True)
    mean=probability@coordinates;delta=coordinates[None]-mean[:,None]
    covariance=torch.einsum('np,npi,npj->nij',probability,delta,delta)
    return mean,covariance+torch.eye(2,device=mask.device)[None]*1e-4


def sqrt_spd(matrix):
    """2x2 positive-definite square root without unstable eigenvector flips."""
    determinant=torch.linalg.det(matrix).clamp(min=1e-12).sqrt()
    trace=matrix.diagonal(dim1=-2,dim2=-1).sum(-1)
    return (matrix+determinant[:,None,None]*torch.eye(2,device=matrix.device)[None])/(trace+2*determinant).sqrt()[:,None,None]


def texture_composite(cnn_mask,reference_images,reference_masks,weights,geometry_share=.45):
    """Warp every fixed-pool reference smoothly, then blend RGB and mask evidence.

    No nearest-reference selection or hard mask threshold occurs here. Geometry
    share is fixed, not an extra trained control. Image scale is uncalibrated.
    """
    if not 0<=geometry_share<=1:raise ValueError('geometry_share must be in [0,1]')
    if len(weights)!=len(reference_images) or not len(weights):raise ValueError('Reference/weight mismatch')
    weights=weights/weights.sum().clamp(min=1e-12)
    reference_mean,reference_cov=mask_moments(reference_masks)
    cnn_mean,cnn_cov=mask_moments(cnn_mask)
    target_mean=geometry_share*cnn_mean+(1-geometry_share)*(weights[:,None]*reference_mean).sum(0,keepdim=True)
    target_cov=geometry_share*cnn_cov+(1-geometry_share)*(weights[:,None,None]*reference_cov).sum(0,keepdim=True)
    transform=sqrt_spd(reference_cov)@torch.linalg.inv(sqrt_spd(target_cov))
    h,w=reference_images.shape[-2:]
    yy,xx=torch.meshgrid(torch.linspace(-1,1,h),torch.linspace(-1,1,w),indexing='ij')
    base=torch.stack([xx,yy],-1).to(reference_images.device)
    grid=torch.einsum('nij,hwj->nhwi',transform,base-target_mean[0])+reference_mean[:,None,None,:]
    # Every same-fuel reference remains in the pool as numeric conditions move.
    warped_rgb=F.grid_sample(reference_images,grid,mode='bicubic',padding_mode='zeros',align_corners=True).clamp(0,1)
    warped_mask=F.grid_sample(reference_masks,grid,mode='bilinear',padding_mode='zeros',align_corners=True)
    texture=(weights[:,None,None,None]*warped_rgb).sum(0,keepdim=True)
    visual_mask=(weights[:,None,None,None]*warped_mask).sum(0,keepdim=True)
    combined_mask=(geometry_share*cnn_mask+(1-geometry_share)*visual_mask).clamp(0,1)
    # Smooth foreground weighting retains recorded colour/texture without a
    # binary cutout; probability is uncalibrated and unsuitable as a PINN label.
    alpha=1-torch.exp(-5*combined_mask)
    return texture*alpha,combined_mask
