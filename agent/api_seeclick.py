import base64
from io import BytesIO
import json
import logging
from pathlib import Path
from PIL import Image
import requests

SEECLICK_API_URL = "http://106.120.101.63:2334/v1/chat/completions"
MODEL_NAME = "seeclick"
BASE_GENERATION_CONFIG = {
    "do_sample": False,
    "max_new_tokens": 1024,
    "top_p": 0.01,
    "temperature": 0.000001,
}


def inference_seeclick(instruction: str, image_path: Path, previous_messages=None, chat=None):
    logging.debug(f"Prompt sent to SeeClick API: {instruction}")
    payload = create_seeclick_payload(prompt=instruction, image=Image.open(image_path),
                                      previous_messages=previous_messages)
    response_seeclick = query_seeclick(payload=payload)
    logging.debug(f"SeeClick API response: {response_seeclick}")
    return response_seeclick


def encode_image(image: Image):
    image = image.convert("RGB")
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    img_str_bytes = base64.b64encode(buffered.getvalue())
    return img_str_bytes.decode("utf-8")


def create_seeclick_payload(prompt: str, image: Image = None, previous_messages=None):
    message_contents = [{"type": "text", "text": prompt}]
    if image:
        message_contents.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{encode_image(image)}"},
            }
        )
    new_message = {"role": "user", "content": message_contents}

    if previous_messages is None:
        previous_messages = []
    messages = [*previous_messages, new_message]
    payload = {"model": MODEL_NAME, **BASE_GENERATION_CONFIG, "messages": messages}
    return payload


def query_seeclick(payload: dict) -> dict:
    while True:
        try:
            http_response = requests.post(SEECLICK_API_URL, json=payload, timeout=10)
            assert (
                    http_response.status_code == 200
            ), f"Request failed with status_code: {http_response.status_code}"
        except:
            pass
        else:
            break
    output = json.loads(http_response.content)
    response = output["choices"][0]
    response = eval(response["message"]["content"])
    return response
