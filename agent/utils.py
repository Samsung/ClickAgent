import base64
import json
import os
from io import BytesIO
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFile


def draw_click(image: Image, click_point: tuple[float, float], output_path):
    image = image.copy()
    w, h = image.size
    radius = int(min(w, h) / 50)
    draw = ImageDraw.Draw(image)
    draw.ellipse(
        xy=[
            int(click_point[0]) - radius,
            int(click_point[1]) - radius,
            int(click_point[0]) + radius,
            int(click_point[1]) + radius,
        ],
        fill=255,
    )
    image.save(output_path)


def draw_rectangle(
        image: Image,
        coordinates: List[int],
        colour: Tuple[int, int, int],
        label: str = None,
):
    path = image.filename
    image = image.copy()
    draw = ImageDraw.Draw(image)
    draw.rectangle(xy=coordinates, fill=None, width=3, outline=colour)

    if label:
        image = add_title_box(image, label)
    image.save(
        os.path.join(
            os.path.dirname(path),
            "bbox_" + os.path.basename(path),
        )
    )
    return image


def add_title_box(img: Image, title: str):
    x, y = img.size
    new_image = Image.new(img.mode, (x, y + 100), (255, 255, 255))
    new_image.paste(img, (0, 100))
    draw = ImageDraw.Draw(new_image)
    draw.text((int(x / 50), 33), title, (0, 0, 0), font_size=32)
    return new_image


def encode_image(image: ImageFile) -> str:
    buffered = BytesIO()
    converted_image = image.convert("RGB")
    converted_image.save(buffered, format="JPEG")
    img_str_bytes = base64.b64encode(buffered.getvalue())
    return img_str_bytes.decode("utf-8")


def add_action(action_log: str, chat):
    with open(action_log + ".jsonl", 'a') as file:
        os.utime(action_log + ".jsonl")
        if chat:
            chat = json.loads(chat)
            print(chat, file=file)
