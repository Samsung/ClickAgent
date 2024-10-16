import base64
import requests
from io import BytesIO
from PIL import Image
import json

MODEL_NAME = "internlm2"
BASE_GENERATION_CONFIG = {
    "top_p": 1,
    "temperature": 0,
}


def encode_image(image):
    image = Image.open(image)
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


def query_internvl(payload: dict, ip) -> dict:
    API_URL = f"http://{ip}/v1/chat/completions"
    while True:
        try:
            http_response = requests.post(API_URL, json=payload, timeout=10)
            assert http_response.status_code == 200, f"Request failed with status_code: {http_response.status_code}"
        except Exception as e:
            print(e)
        else:
            break
    output = json.loads(http_response.content)
    return output["choices"][0]
