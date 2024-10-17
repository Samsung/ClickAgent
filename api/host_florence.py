import torch
import uvicorn
import base64
import asyncio
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from fastchat.serve.model_worker import BaseModelWorker, worker_id
from fastchat.utils import build_logger
import torch
from florence_agent import FlorenceAgent
import albumentations as A

from torch.utils.data import DataLoader
from tqdm import tqdm

from data import FlorenceDataset, collator
import numpy as np
from functools import partial

logger = build_logger("model_worker", f"model_worker_{worker_id}.log")
app = FastAPI()


class FlorenceWorker(BaseModelWorker):
    def __init__(
            self,
            controller_addr: str,
            worker_id: str,
            limit_worker_concurrency: int,
            worker_host: str, worker_port: int,
            path_florence: str
    ):
        self.worker_addr = f"http://{worker_host}:{worker_port}"
        super().__init__(
            controller_addr,
            self.worker_addr,
            worker_id,
            "florence",
            [],
            limit_worker_concurrency,
        )
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'

        self.load_model(path_florence)

    def load_model(
            self,
            path_florence
    ):
        
        self.agent = FlorenceAgent(path_florence, device=self.device, prediction_format="point").eval()

        return None

    async def generate(
            self,
            params: dict,
    ):
        try:
            print("--------------------")
            prompt = params["prompt"].lower()
            print(prompt)
            metadata = [
                {
                    "generated_command":  ("What to do to execute the command? " + prompt.strip()).lower(),
                    "image": load_image(params["image"])

                }
            ]
            dataset = FlorenceDataset(
                metadata,
                self.agent.processor,
                img_root="",
                mode="inference",
            )

            collator_ = partial(collator, pad_token_id=self.agent.processor.tokenizer.pad_token_id)
            dataloader = DataLoader(
                dataset, batch_size=1, collate_fn=collator_, shuffle=False
            )
            prediction = None
            click_point = None
            box = None
            with tqdm(
                enumerate(dataloader),
                total=len(dataloader),
                bar_format="{l_bar}{bar:20}{r_bar}",
            ) as bar:
                for batch_id, batch in bar:
                    image_sizes = batch.pop("image_size")
                    needs_box_click = batch.pop("needs_box_click")
                    batch = {k: v.to(self.device) for k, v in batch.items()}

                    predictions = self.agent.predict(
                        batch, image_sizes, max_new_tokens=64, return_bbox=True, num_beams=1, do_sample=False
                    )
                    type_text_prediction = predictions[0]["type_text"]
                    action = predictions[0]["action"]
                    prediction = predictions[0]
                    box = [int(xy) for xy in predictions[0]["click_point"]]
                    x, y = box
                    box = [x - 1, y - 1, x + 1, y + 1]

                    if box != [0, 0, 0, 0]:
                        # Restore prediction to original size and location
                        normalizer = A.Compose(
                            [
                                A.Crop(
                                    *dataset.metadata[0]["original_image_location"]
                                ),
                                A.Resize(
                                    *dataset.metadata[0]["original_image_shape"][:2]
                                ),
                            ],
                            bbox_params=A.BboxParams(
                                format="pascal_voc", label_fields=["class_labels"]
                            ),
                        )
                        normalized = normalizer(
                            image=np.zeros((768, 768)),
                            bboxes=[box],
                            class_labels=[0],
                        )
                        box = normalized["bboxes"][0]    

                    click_point = (
                        (box[0] + box[2]) // 2,
                        (box[1] + box[3]) // 2,
                    )
                    break
            
        except Exception as e:
            logger.exception("Error encountered during generation")
            return {
                "exit_code": 1,
                "text": "",
                "error_code": str(e),
            }
        return {
            "exit_code": 0,
            "action_type": prediction["action"],
            "click_point": click_point,
            "type_text": prediction["type_text"],
            "box": box
        }


def load_image(image_file, input_size=448, max_num=12):
    image = base64.b64decode(image_file)
    np_image = np.frombuffer(image, dtype=np.uint8)
    return np_image


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


@app.post("/worker_generate")
async def api_generate(request: Request):
    await acquire_worker_semaphore()
    params = await request.json()

    output = await worker.generate(params)
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
    parser.add_argument(
        "--path_florence",
        type=str,
        default="Samsung/TinyClick"
    )
    args = parser.parse_args()

    worker = FlorenceWorker(
        args.controller_address,
        worker_id,
        args.limit_worker_concurrency,
        args.host,
        args.port,
        args.path_florence
    )

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")