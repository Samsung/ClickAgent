import base64
import json
from io import BytesIO

import requests
from PIL import Image

API_URL = 'http://0.0.0.0:9000/v1/chat/completions'

MODEL_NAME = "internlm2"
BASE_GENERATION_CONFIG = {
    "top_p": 1,
    "temperature": 0,
}


def encode_image(image):
    image = Image.open(BytesIO(base64.b64decode(image)))
    image = image.convert('RGB')
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    img_str_bytes = base64.b64encode(buffered.getvalue())
    return img_str_bytes.decode("utf-8")


def create_internvl_payload(prompt: str, images: list, previous_messages=None):
    base64_images = [encode_image(image) for image in images]
    message_contents = [{
        "type": "text",
        "text": prompt
    }]
    for base64_image in base64_images:
        message_contents.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_image}"
            }
        })
    new_message = {
        "role": "user",
        "content": message_contents
    }

    if previous_messages is None:
        previous_messages = []
    messages = [
        *previous_messages,
        new_message
    ]
    payload = {
        "model": MODEL_NAME,
        **BASE_GENERATION_CONFIG,
        "messages": messages
    }
    return payload


def query_internvl(payload: dict) -> dict:
    while True:
        try:
            http_response = requests.post(API_URL, json=payload, timeout=25)
            assert http_response.status_code == 200, f"Request failed with status_code: {http_response.status_code}"
        except Exception as e:
            print(e)
        else:
            break
    output = json.loads(http_response.content)
    print(output)
    return output["choices"][0]
