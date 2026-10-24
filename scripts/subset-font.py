"""Build the optional UI font asset with fonttools and brotli, outside app dependencies."""

import argparse
from pathlib import Path

from fontTools import subset


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Path to an OFL-licensed Noto Sans SC font")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    text = set(chr(code) for code in range(32, 127))
    for directory in (
        root / "apps/web/app",
        root / "services/api/src/tooldawn",
    ):
        for path in directory.rglob("*"):
            if path.suffix in {".vue", ".ts", ".json", ".py"}:
                text.update(path.read_text(encoding="utf-8"))
    text.update("，。；：？！、（）《》“”‘’…—·")
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["*"]
    font = subset.load_font(str(args.source), options)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(text="".join(sorted(text)))
    subsetter.subset(font)
    output = root / "apps/web/public/fonts/tooldawn-sans-sc.woff2"
    subset.save_font(font, str(output), options)
    print(f"UI font subset ready: {output.stat().st_size // 1024} KiB")


if __name__ == "__main__":
    main()
