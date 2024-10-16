import requests
from PIL import Image
import json

from utils import encode_image


def create_analysis_payload(instruction: str, images: list):
    base64_images = [encode_image(image) for image in images]
    payload = {
        "instruction": instruction,
        "images": base64_images,
    }
    return payload


def query_analysis(payload: dict, ip: str) -> dict:
    url = f'http://{ip}/worker_generate_analysis'
    i = 0
    while True:
        try:
            http_response = requests.post(url, json=payload, timeout=200)
            assert http_response.status_code == 200, f"Request failed with status_code: {http_response.status_code}"
        except Exception as e:
            print(e)
            if i == 10:
                break
            i += 1
        else:
            break
    output = json.loads(http_response.content)
    return output


def create_qwen_payload(instruction, action_history, images: list, use_qwen: bool):
    base64_images = [encode_image(image) for image in images]
    payload = {
        "instruction": instruction,
        "action_history": action_history,
        "image": base64_images[0],
        "use_qwen": use_qwen
    }
    return payload


def create_qwen_payload_for_action(prompt: str, image: Image, instruction: str, action_history, use_eval: bool,
                                   prompt_reflection, prompt_init_chat):
    base64_images = encode_image(image)
    payload = {
        "prompt": prompt,
        "instruction": instruction,
        "action_history": action_history,
        "image": base64_images,
        "use_eval": use_eval,
        "prompt_reflection": prompt_reflection,
        "prompt_init_chat": prompt_init_chat
    }
    return payload


def query_qwen(payload: dict, ip: str) -> dict:
    url = f'http://{ip}/worker_generate_plan'
    i = 0
    while True:
        try:
            http_response = requests.post(url, json=payload, timeout=200)
            assert http_response.status_code == 200, f"Request failed with status_code: {http_response.status_code}"
        except Exception as e:
            print(e)
            if i == 10:
                break
            i += 1
        else:
            break
    output = json.loads(http_response.content)

    return output
