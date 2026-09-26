from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
        Path(r"C:\Windows\Fonts\segoeuib.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def main() -> None:
    output = Path(__file__).with_name("assets") / "app.ico"
    output.parent.mkdir(parents=True, exist_ok=True)

    size = 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (10, 10, size - 10, size - 10),
        radius=46,
        fill="#0f766e",
    )
    draw.rectangle((42, 54, 214, 158), fill="#ffffff")
    font = load_font(76)
    draw.text((55, 65), "JM", font=font, fill="#0f766e")
    draw.polygon(
        [(128, 216), (82, 168), (110, 168), (110, 136), (146, 136), (146, 168), (174, 168)],
        fill="#ffffff",
    )
    image.save(
        output,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(output)


if __name__ == "__main__":
    main()
