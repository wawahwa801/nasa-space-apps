"""Small next-frame CNN. Run commands from the repository root."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

import cv2
import numpy as np
from PIL import Image
import torch
from torch import nn

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
OUT = ROOT / 'artifacts'
SOURCE = 'https://images-assets.nasa.gov/video/GRC-2021-CN-00008/GRC-2021-CN-00008~mobile.mp4'


def model():
    # 1,827 parameters; image-only pipeline demonstration, not a heat-flux model.
    return nn.Sequential(nn.Conv2d(3, 8, 3, padding=1), nn.ReLU(),
                         nn.Conv2d(8, 16, 3, padding=1), nn.ReLU(),
                         nn.Conv2d(16, 3, 3, padding=1), nn.Sigmoid())


def prepare(args):
    DATA.mkdir(exist_ok=True)
    video = Path(args.video) if args.video else DATA / 'saffire-v.mp4'
    if not args.video and not video.exists():
        # Cap downloads at 30 MiB; never crawl the whole archive.
        with urllib.request.urlopen(SOURCE, timeout=60) as response:
            content = response.read(30 * 1024 * 1024 + 1)
        if len(content) > 30 * 1024 * 1024:
            raise ValueError('Video exceeds 30 MiB cap')
        video.write_bytes(content)
    capture = cv2.VideoCapture(str(video))
    fps = capture.get(cv2.CAP_PROP_FPS)
    frames = []
    times = []
    try:
        for i in range(args.frames):
            capture.set(cv2.CAP_PROP_POS_MSEC, (args.start + i * args.interval) * 1000)
            ok, frame = capture.read()
            if not ok:
                break
            frames.append(cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), (64, 64)))
            times.append(args.start + i * args.interval)
    finally:
        capture.release()
    if len(frames) < 12:
        raise ValueError('Need at least 12 decoded frames; check video and time range')
    destination = DATA / args.run_id
    destination.mkdir(exist_ok=True)
    np.save(destination / 'frames.npy', np.array(frames))
    provenance = dict(run_id=args.run_id, video=str(video), source=SOURCE if not args.video else args.source,
                      sha256=hashlib.sha256(video.read_bytes()).hexdigest(), fps=fps,
                      timestamps_seconds=times, shape=[len(frames), 64, 64, 3],
                      label='next RGB frame; no calibrated heat flux or environmental labels')
    (destination / 'provenance.json').write_text(json.dumps(provenance, indent=2))
    Image.fromarray(frames[0]).save(destination / 'first-frame.png')
    print(json.dumps(provenance, indent=2))


def load(run):
    return torch.from_numpy(np.load(DATA / run / 'frames.npy')).permute(0, 3, 1, 2).float() / 255


def train(args):
    if args.epochs < 1:
        raise ValueError('epochs must be positive')
    torch.manual_seed(42)
    torch.set_num_threads(2)
    frames = load(args.run_id)
    if args.val_run:
        if args.val_run == args.run_id:
            raise ValueError('Validation run must differ from training run')
        other = load(args.val_run)
        x, y, vx, vy = frames[:-1], frames[1:], other[:-1], other[1:]
        scope = 'Separate run: confirm genuinely independent experiment IDs'
    else:
        cut = int(len(frames) * .75)
        x, y = frames[:cut-1], frames[1:cut]
        vx, vy = frames[cut:-1], frames[cut+1:]
        scope = 'Same-video temporal holdout; smoke test only, not independent validation'
    net = model()
    optimizer = torch.optim.Adam(net.parameters(), lr=.001)
    loss_fn = nn.MSELoss()
    for epoch in range(args.epochs):
        net.train()
        for indices in torch.randperm(len(x)).split(8):
            optimizer.zero_grad()
            loss = loss_fn(net(x[indices]), y[indices])
            loss.backward()
            optimizer.step()
    net.eval()
    with torch.no_grad():
        predicted = net(vx)
        mse = loss_fn(predicted, vy).item()
        baseline = loss_fn(vx, vy).item()
    OUT.mkdir(exist_ok=True)
    torch.save(net.state_dict(), OUT / 'tiny.pt')
    report = dict(parameters=sum(p.numel() for p in net.parameters()), epochs=args.epochs,
                  train_pairs=len(x), validation_pairs=len(vx), validation_mse=mse,
                  persistence_mse=baseline, evaluation=scope, seed=42)
    (OUT / 'metrics.json').write_text(json.dumps(report, indent=2))
    panels = torch.cat([vx[0], predicted[0], vy[0]], dim=2)
    Image.fromarray((panels.permute(1, 2, 0).numpy()*255).astype('uint8')).save(OUT / 'comparison.png')
    print(json.dumps(report, indent=2))


def predict(args):
    net = model()
    net.load_state_dict(torch.load(OUT / 'tiny.pt', map_location='cpu', weights_only=True))
    net.eval()
    frame = np.array(Image.open(args.image).convert('RGB').resize((64, 64)))
    tensor = torch.from_numpy(frame).permute(2, 0, 1).float().unsqueeze(0) / 255
    with torch.no_grad():
        result = net(tensor)[0].permute(1, 2, 0).numpy()
    Image.fromarray((result * 255).astype('uint8')).save(args.output)
    print(f'Saved {args.output}; RGB appearance prediction only')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--video', help='Local raw PSI video; otherwise downloads public SAFFIRE-V demo')
    prep.add_argument('--source', default='Local import: supply original NASA URL')
    prep.add_argument('--run-id', default='saffire-v-demo')
    prep.add_argument('--frames', type=int, default=80)
    prep.add_argument('--start', type=float, default=0)
    prep.add_argument('--interval', type=float, default=.25)
    prep.set_defaults(func=prepare)
    fit = sub.add_parser('train')
    fit.add_argument('--run-id', default='saffire-v-demo')
    fit.add_argument('--val-run')
    fit.add_argument('--epochs', type=int, default=10)
    fit.set_defaults(func=train)
    infer = sub.add_parser('predict')
    infer.add_argument('image')
    infer.add_argument('--output', default=str(OUT / 'prediction.png'))
    infer.set_defaults(func=predict)
    args = parser.parse_args()
    if hasattr(args, 'frames') and (args.frames < 12 or args.interval <= 0 or args.start < 0):
        parser.error('frames >= 12, interval > 0, and start >= 0 required')
    if hasattr(args, 'run_id') and (Path(args.run_id).name != args.run_id or args.run_id in ('.', '..')):
        parser.error('run-id must be a single directory name')
    args.func(args)


if __name__ == '__main__':
    main()
