import base64
import json
import string
import time
from io import BytesIO

import requests
from PIL import Image

API_URL = 'http://127.0.0.1:21006/worker_generate'


def encode_image(image: str):
    image = Image.open(BytesIO(base64.b64decode(image)))
    image = image.convert('RGB')
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    img_str_bytes = base64.b64encode(buffered.getvalue())
    return img_str_bytes.decode("utf-8")


def create_local_florence_payload(prompt: str, images: list):
    base64_images = [encode_image(image) for image in images]
    prompt = prompt.translate(str.maketrans('', '', string.punctuation))
    payload = {
        "prompt": prompt.lower(),
        "image": base64_images[0]
    }
    return payload


def query_florence(payload: dict) -> tuple:
    print("inside query_florence => api/api_florence")
    while True:
        try:
            time.sleep(2)
            http_response = requests.post(API_URL, json=payload, timeout=20)
            print("query_florence => api/api")
            assert http_response.status_code == 200, f"Request failed with status_code: {http_response.status_code}"
        except:
            print("timeout => florence")
            pass
        else:
            break
    output = json.loads(http_response.content)
    print(output)
    return output
