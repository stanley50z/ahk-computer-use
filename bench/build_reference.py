"""Build the Adobe Illustrator Pen Tool reference image from Cloud9's official icon.

The reference is third-party logo artwork, so this repository does not ship it. Download Cloud9's brand assets from
https://cloud9.gg/brand-assets/ and run once per checkout:

    python bench/build_reference.py "<package>/PNG/Icon/C9_Icon_Blue_AllMode.png"

The output, bench/assets/illustrator-pen-tool/Cloud9-Reference.png, is gitignored. Both the source and the output are
checked against fixed SHA-256 digests, so every checkout grades against identical pixels.
"""

import argparse
import hashlib
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'bench/assets/illustrator-pen-tool/Cloud9-Reference.png'
SOURCE_SHA256 = '49d3d3dd25a58c216fa92557e4d15423bf599952ccbc97a49dd0ca29986ecebb'
REFERENCE_SHA256 = '03dd860809cbfa143c35b50bd78fbdb8e43346e47d76e9aba5afc94a4e00a32c'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# Area-averages the icon's alpha coverage to 550 x 551, keeps the official solid #00AEEF and composites it at
# (143,120) on an 800 x 800 white canvas, matching the original reference's framing. Raises ValueError on any
# fingerprint mismatch and leaves no output behind.
def build(source, output=REFERENCE):
    if sha256(source) != SOURCE_SHA256:
        raise ValueError(f'{source} is not the official C9_Icon_Blue_AllMode.png (SHA-256 {SOURCE_SHA256})')
    with Image.open(source) as icon:
        coverage = icon.getchannel('A').resize((550, 551), Image.Resampling.BOX)
    logo = Image.new('RGBA', (550, 551), (0, 174, 239, 255))
    logo.putalpha(coverage)
    canvas = Image.new('RGBA', (800, 800), 'white')
    canvas.alpha_composite(logo, (143, 120))
    canvas.convert('RGB').save(output, format='PNG', dpi=(72, 72))
    if sha256(output) != REFERENCE_SHA256:
        Path(output).unlink()
        raise ValueError(f'built reference does not match SHA-256 {REFERENCE_SHA256}; check the Pillow version')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source', type=Path, help='path to the official C9_Icon_Blue_AllMode.png')
    args = parser.parse_args()
    try:
        print(build(args.source))
    except ValueError as error:
        sys.exit(str(error))


if __name__ == '__main__':
    main()
