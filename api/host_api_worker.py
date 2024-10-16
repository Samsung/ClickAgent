import asyncio
import base64
import copy
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import torch
import uvicorn
from PIL import Image
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from fastchat.serve.model_worker import BaseModelWorker, worker_id
from fastchat.utils import build_logger
from transformers import GenerationConfig

from api_florence import create_local_florence_payload, query_florence
from api_internvl import create_internvl_payload, query_internvl

logger = build_logger("model_worker", f"model_worker_{worker_id}.log")
app = FastAPI()


class ApiWorker(BaseModelWorker):
    def __init__(
            self,
            controller_addr: str,
            worker_id: str,
            limit_worker_concurrency: int,
            worker_host: str, worker_port: int,
    ):
        self.worker_addr = f"http://{worker_host}:{worker_port}"
        super().__init__(
            controller_addr,
            self.worker_addr,
            worker_id,
            "qwenvl",
            [],
            limit_worker_concurrency,
        )
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'

        self.torch_type = torch.bfloat16

    async def generate_decision(
            self,
            params: dict,
    ):
        try:
            reflect = self.get_reflection(params)

        except Exception as e:
            logger.exception("Error encountered during generation")
            return {
                "exit_code": 1,
                "text": "",
                "error_code": str(e),
            }
        return {
            "exit_code": 0,
            "text": reflect,
        }

    def get_reflection(self, params: dict):
        if not params["use_eval"]:
            return "failure", "", "", ""
        print("--------------------")
        start = time.time()
        text = f"Please describe the screenshot above in details.\n"
        end = time.time()
        print(end - start)
        start = time.time()
        chat_description = init_describe_chat()
        payload = create_internvl_payload(text, [params["image"]], chat_description)
        output_description = query_internvl(payload=payload)["message"]["content"] + "\n"
        chat_description = add_response("user", text, chat_description)
        chat_description = add_response("assistant", output_description, chat_description)
        print("-------" + output_description)
        print("end decsription---")
        end = time.time()
        chat_eval = init_eval_chat(params["prompt_init_chat"])
        prompt = [build_final_eval_v3_final_prompt(reflection, output_description) for reflection in
                  params["prompt_reflection"]]
        payload = [create_internvl_payload(prompt[0], [], chat_eval[0]),
                   create_internvl_payload(prompt[1], [], chat_eval[1])]

        print("internvl describe", end - start)
        start = time.time()

        with ThreadPoolExecutor(max_workers=len(payload)) as executor:
            futures = [executor.submit(query_internvl, payl) for payl in payload]

        output_reflect = [future.result()['message']['content'] + "\n" for future in futures]
        statuses = []
        reflects = []
        rates = []
        answer = None
        for i, out in enumerate(output_reflect):
            print("#" * 50)
            print(out)
            print("#" * 50)
            status = re.search(r"Status:(.*)", out)
            if status:
                statuses.append(status.group(1).strip())
            reflect = re.search(r"Thoughts:(.*)", out)
            if reflect:
                reflects.append(reflect.group(1).strip())
            rate = re.search(r"Rate:(.*)", out)
            if rate:
                rates.append(rate.group(1).strip())
            answer = re.search(r"Answer:(.*)\n", out)
            if answer:
                answer = answer.group(1).strip()
            print("Answer in reflection: ", answer)
            chat_eval[i] = add_response("user", prompt[i], chat_eval[i])
            chat_eval[i] = add_response("assistant", out, chat_eval[i])
        end = time.time()
        print("reflecrion", end - start)

        return statuses, reflects, answer, output_description, chat_eval, rates, chat_description

    async def generate_action(
            self,
            params: dict,
    ):
        try:
            status_reflect, reflect_done, answer, output_description, chat_eval, rates, chat_description = (
                self.get_reflection(params)
            )
            if "success" in status_reflect[0].lower() and "success" in status_reflect[1].lower() and (
                    int(rates[0]) + int(rates[1])) >= 10:
                return {
                    "exit_code": 0,
                    "summary": "",
                    "thought": "",
                    "action": "",
                    "response": "",
                    "success": '\n'.join(status_reflect),
                    "command": "",
                    "groundtruth": "",
                    "reflection_status": '\n'.join(reflect_done),
                    "description": "",
                    "prompt": "",
                    "bbox": None,
                    "chat_action": "",

                    "chat_eval": json.dumps(chat_eval[0]),
                    "chat_eval_1": json.dumps(chat_eval[1]),
                    "rates": rates,
                    "chat_description": json.dumps(chat_description),
                    "answer": answer

                }
            chat_action = init_action_chat()
            prompt = f"""### Screenshot Information ###
This is description of screenshot. You can generate your output based on it.
{output_description} 
### Background ###
{params["prompt"]}"""
            payload = create_internvl_payload(prompt, [params["image"]], chat_action)
            start = time.time()
            output_action = query_internvl(payload=payload)
            print(output_action)
            output_action = output_action["message"]["content"] + "\n"
            chat_action = add_response("user", prompt, chat_action)
            chat_action = add_response("assistant", output_action, chat_action)
            print("#" * 10, output_action, "#" * 10)
            summary = re.search(r"Operation:(.*?)\n", output_action)
            if summary:
                summary = summary.group(1).strip()
            thought = re.search(r"Thought:(.*?)\n", output_action)
            if thought:
                thought = thought.group(1).strip()
            action = re.search(r"Action:(.*)\n", output_action)
            if action:
                action = action.group(1).strip()
            command = re.search(r"Command:(.*)\n", output_action)
            if command:
                command = command.group(1).strip()
            groundtruth = re.search(r"Ground truth:(.*)\n", output_action)
            if groundtruth:
                groundtruth = groundtruth.group(1).strip()
            description = re.search(r"Description:(.*)\n", output_action)
            if description:
                description = description.group(1).strip()
            answer = re.search(r"Answer:(.*)\n", output_action)
            if answer:
                answer = answer.group(1).strip()
            print("answer: => ", answer)

            end = time.time()
            print("action gen", end - start)

            response = None
            if command and (
                    "click" in command.lower() or "type" in command.lower() or "click" in action.lower() or "type" in action.lower()):
                description = description.lower()
                description = description.replace("address bar", "url address bar")

                if description:
                    payload_florence = create_local_florence_payload("click " + description, [params["image"]])
                else:
                    print("Description is empty, command: ", command)
                    payload_florence = create_local_florence_payload(str(command), [params["image"]])

                print("Query florence after payload")
                response = query_florence(payload_florence)

            end = time.time()
            print("florence", end - start)
        except Exception as e:
            logger.exception("Error encountered during generation")
            return {
                "exit_code": 1,
                "text": "",
                "error_code": str(e),
            }

        return {
            "exit_code": 0,
            "summary": summary,
            "thought": thought,
            "action": action,
            "response": response["click_point"] if response and "click_point" in response else None,
            "bbox": response["box"] if response and "box" in response else None,
            "success": '\n'.join(status_reflect),
            "command": command,
            "groundtruth": groundtruth,
            "reflection_status": '\n'.join(reflect_done),
            "description": description,
            "prompt": prompt,
            "chat_action": json.dumps(chat_action),
            "chat_eval": json.dumps(chat_eval[0]),
            "chat_eval_1": json.dumps(chat_eval[1]),
            "rates": rates,
            "chat_description": json.dumps(chat_description),
            "answer": answer

        }


def remove_punctuation(input_string):
    import string
    return ''.join(ch for ch in input_string if ch not in set(string.punctuation))


def get_prompt_numeral(command, operation, thought, action):
    prompt = f"""Check if Command has ordinal numbers, if yes try to specify which UI element should be clicked. For example is it link or search bar or image etc.
### Command ###
{command}
### Operation ###
{operation}
### Thought ###
{thought}
### Action ###
{action}
### Output format ###
Your output format is:
Status: <Are there any ordinal numbers in command> YES/NO
Command: <If there is ordinal numbers in command return brief description of UI element which should be clicked based on command, operation, thought and action, return short description not long>
(Please use English to output)
"""

    return prompt


generation_config = GenerationConfig.from_dict(
    {
        "chat_format": "chatml",
        "do_sample": False,
        "eos_token_id": 151643,
        "max_new_tokens": 2048,
        "max_window_size": 6144,
        "pad_token_id": 151643,
        "repetition_penalty": 1.2,
        "transformers_version": "4.31.0",
    }
)


def add_response(role, prompt, chat_history):
    new_chat_history = copy.deepcopy(chat_history)

    content = [
        {
            'type': 'text',
            'text': prompt
        },
    ]
    new_chat_history.append({'role': role, 'content': content})
    return new_chat_history


def init_describe_chat():
    operation_history = []
    system_prompt = ('You are a helpful AI phone screenshot captioner. I need you to help me describe the phone '
                     'screenshot in great detail. Describe every UI element you see and is clickable and every text '
                     'you see. Try to recognize what application is opened now.')
    operation_history.append({'role': 'system', 'content': [{'type': 'text', 'text': system_prompt}]})
    return operation_history


def init_action_chat():
    operation_history = []
    system_prompt = ('You are a helpful AI american mobile phone operating assistant. You need to help me operate the '
                     'phone to complete the user\'s instruction. Do not allow location sharing and cookies.')
    operation_history.append({'role': 'system', 'content': [{'type': 'text', 'text': system_prompt}]})
    return operation_history


def init_numeral_chat():
    operation_history = []
    system_prompt = ('You are a helpful AI mobile phone operating assistant. You need to help me caption the image, '
                     'say if there is numeral, and describe UI element which should be clicked.')
    operation_history.append({'role': 'system', 'content': [{'type': 'text', 'text': system_prompt}]})
    return operation_history


def init_eval_chat(chats):
    operation_history = [[{'role': 'system', 'content': [{'type': 'text', 'text': chats[0]}]}],
                         [{'role': 'system', 'content': [{'type': 'text', 'text': chats[1]}]}]]

    return operation_history


def build_final_eval_v3_final_prompt(
        prompt, cap
):
    prompt = f"""The detailed final state of the screen:
```md
{cap}
```
{prompt}"""
    return prompt


def load_image(image_file):
    image = Image.open(BytesIO(base64.b64decode(image_file)))
    image = image.convert('RGB')
    return image


def release_worker_semaphore():
    worker.semaphore.release()


def acquire_worker_semaphore():
    if worker.semaphore is None:
        worker.semaphore = asyncio.Semaphore(worker.limit_worker_concurrency)
    return worker.semaphore.acquire()


def create_background_tasks():
    background_tasks = BackgroundTasks()
    background_tasks.add_task(release_worker_semaphore)
    return background_tasks


@app.post("/worker_generate_decision")
async def api_generate(request: Request):
    params = await request.json()
    await acquire_worker_semaphore()
    output = await worker.generate_decision(params)
    release_worker_semaphore()
    return JSONResponse(output)


@app.post("/worker_generate_plan")
async def api_generate(request: Request):
    params = await request.json()
    await acquire_worker_semaphore()
    output = await worker.generate_action(params)
    release_worker_semaphore()
    return JSONResponse(output)


@app.post("/worker_get_status")
async def api_get_status(request: Request):
    return worker.get_status()


@app.post("/count_token")
async def api_count_token(request: Request):
    params = await request.json()
    return worker.count_token(params)


@app.post("/worker_get_conv_template")
async def api_get_conv(request: Request):
    return worker.get_conv_template()


@app.post("/model_details")
async def api_model_details(request: Request):
    return {"context_length": worker.context_len}


@app.get("/test_connection")
async def api_test_connection(request: Request):
    return "success"


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=21002
    )
    parser.add_argument(
        "--worker-address",
        type=str,
        default="0.0.0.0"
    )
    parser.add_argument(
        "--controller-address",
        type=str,
        default="http://localhost:21001"
    )
    parser.add_argument(
        "--conv-template",
        type=str,
        default=None,
        help="Conversation prompt template."
    )
    parser.add_argument(
        "--limit-worker-concurrency",
        type=int,
        default=5,
        help="Limit the model concurrency to prevent OOM.",
    )
    args = parser.parse_args()

    worker = ApiWorker(
        args.controller_address,
        worker_id,
        args.limit_worker_concurrency,
        args.host,
        args.port
    )

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
