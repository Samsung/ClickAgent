import requests
from PIL import Image
import json

from utils import encode_image


def create_local_florence_payload(prompt: str, image: Image):
    base64_image = encode_image(image)
    payload = {
        "prompt": prompt,
        "image": base64_image
    }
    return payload


def query_florence(payload: dict, ip: str) -> tuple:
    url = f'http://{ip}/worker_generate'
    while True:
        try:
            http_response = requests.post(url, json=payload, timeout=10)
            assert http_response.status_code == 200, f"Request failed with status_code: {http_response.status_code}"
        except:
            pass
        else:
            break
    output = json.loads(http_response.content)
    points = output["click_point"]
    return points


def query_florence_box(payload: dict, ip: str) -> tuple:
    url = f'http://{ip}/worker_generate'
    while True:
        try:
            http_response = requests.post(url, json=payload, timeout=3)
            assert http_response.status_code == 200, f"Request failed with status_code: {http_response.status_code}"
        except:
            pass
        else:
            break
    output = json.loads(http_response.content)
    points = output["box"]
    return points
