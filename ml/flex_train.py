"""Separate validation-selected FLEX methanol experiment; never pool with PMMA."""
import argparse
from bass_train import run
from flex_images import ROOT,FIELDS
from flame import OUT

ART=OUT/'flex-study'

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--epochs',type=int,default=400);a=p.parse_args()
    run(a.epochs,work=ROOT,art=ART,fields=FIELDS,version='flex-methanol-v1',
        stage='25–65% of reported burn duration after Test GMT, with post-reported-burn camera baseline; timestamp is a burn-start proxy needing verification',
        mask_note='weak threshold on smoothed background-subtracted 16-bit camera-B signal; not manually calibrated flame ground truth')
