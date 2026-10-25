"""Run either accelerated path over DDS files using a bounded worker pool."""
import argparse
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from herta_bc7 import BC7Engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+', type=Path)
    parser.add_argument('--mode', choices=['similarity', 'pixels'], default='similarity')
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--grid', type=int, default=64)
    args = parser.parse_args()
    engine = BC7Engine()
    start = perf_counter()
    for path, result in engine.analyze_files(
            args.paths, mode=args.mode, workers=args.workers, grid=args.grid):
        details = (result.sha256 if args.mode == 'pixels'
                   else f'{len(result.values)} RGB mean values')
        print(f'{path}: {result.width}x{result.height} {details}')
    print(f'{args.mode}: {perf_counter() - start:.3f}s')


if __name__ == '__main__':
    main()
