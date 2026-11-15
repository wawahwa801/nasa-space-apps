"""Display alignment only: integer translation preserves flame scale and RGB."""
import cv2
import numpy as np


def centre_flame(image):
    """Centre the largest smoothed luminous region; leave empty images unchanged.

    This is an approximate display heuristic, not a physical flame segmentation.
    Border exclusions suppress camera-edge reflections in the FLEX-2 view.
    """
    array=np.asarray(image,dtype='uint8')
    if array.ndim!=3 or array.shape[2]!=3:raise ValueError('Expected RGB image')
    h,w=array.shape[:2]
    smooth=cv2.GaussianBlur(array.astype('float32'),(0,0),3)
    # Blue/purple shells are more useful than white igniter highlights or red
    # reflections. Generic intensity also supports monochromatic CNN outputs.
    candidates=[((smooth[:,:,2]-smooth[:,:,1]>3)&(smooth[:,:,2]>8),'blue-shell signal'),
        (smooth.max(2)>8,'luminous signal')]
    selected=None
    for signal,method in candidates:
        foreground=signal.astype('uint8')
        foreground[:max(1,round(h*.04))]=0
        foreground[round(h*.86):]=0
        foreground[:,:max(1,round(w*.04))]=0
        foreground[:,round(w*.96):]=0
        count,labels,stats,_=cv2.connectedComponentsWithStats(foreground,8)
        adequate=[s for s in stats[1:] if s[cv2.CC_STAT_AREA]>=1000 and .4<=s[2]/s[3]<=2.5]
        if adequate:
            selected=max(adequate,key=lambda s:s[cv2.CC_STAT_AREA]);break
    if selected is None:
        return array.copy(),dict(found=False,shift_pixels=[0,0],method='No adequate luminous region; image retained')
    x,y,bw,bh,area=map(int,selected)
    dx=int(round((w-1)/2-(x+(bw-1)/2)))
    dy=int(round((h-1)/2-(y+(bh-1)/2)))
    aligned=cv2.warpAffine(array,np.float32([[1,0,dx],[0,1,dy]]),(w,h),flags=cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT,borderValue=0)
    return aligned,dict(found=True,shift_pixels=[dx,dy],source_bounds=[x,y,bw,bh],
        detection=method,method='Integer translation of detected luminous-region bounds; no resizing or recolouring')
