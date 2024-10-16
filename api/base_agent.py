import re
import torch
from torch import nn
from transformers import AutoProcessor, AutoModelForCausalLM
from peft import LoraConfig, get_peft_model


class BaseAgent(nn.Module):
    """
    Base class for single-step agents with usage of Huggingface models.
    """

    ACTIONS = ["swipe", "click", "type"]

    def __init__(
        self, base_model: str, device: str = "cuda", prediction_format: str = "box"
    ) -> None:
        """
        Args:
            base_model: HF model name or path to local checkpoint
        """
        super(BaseAgent, self).__init__()

        self.processor = AutoProcessor.from_pretrained(
            base_model, trust_remote_code=True
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            base_model,
            trust_remote_code=True
        ).to(device)
        self.prediction_format = prediction_format

    def configure_lora(self, lora_cfg: dict):
        """Configures LoRA adapter for base model.

        Args:
            lora_cfg: Dict with lora configuration arguments.
        """
        lora_config = LoraConfig(
            r=lora_cfg["rank"],
            lora_alpha=lora_cfg["rank"] * 2,
            target_modules=lora_cfg["target_modules"],
            lora_dropout=lora_cfg["dropout"],
            bias=lora_cfg["bias"],
            task_type=lora_cfg["task_type"],
        )
        self.model = get_peft_model(self.model, lora_config)
        self.model.print_trainable_parameters()

    def forward(self, batch: dict):
        output = self.model(**batch)
        return output

    def predict(
        self, batch: dict, image_sizes: list, return_bbox: bool = False, **kwargs
    ):
        raise NotImplementedError

    def process_outputs(self, predictions: list):
        raise NotImplementedError

    def _post_process_generation_box(
        self, text: str, image_size: tuple[int], return_bbox=False
    ):
        """Function that decodes model's generation into action json.

        Args:
            text: single generated sample
            image_size: corresponding image size
        """
        pattern = r"</s><s>(<[^>]+>|[^<\s]+)\s*([^<]*?)(<loc_\d+>.*)"
        box_pattern = r"<loc_(\d+)><loc_(\d+)><loc_(\d+)><loc_(\d+)>"
        match = re.search(pattern, text)

        if not match or (action := match.group(1)) not in self.ACTIONS:
            return {
                "action": "none",
                "type_text": None,
                "click_point": [0, 0, 0, 0] if return_bbox else (0, 0),
            }

        type_text = match.group(2).strip() if match.group(2) else ""

        result = {
            "action": action,
            "type_text": type_text.strip() if type_text else None,
        }

        try:
            location = list(re.finditer(box_pattern, text))
            if len(location) > 0:
                bbox_bins = [
                    [int(_bboxes_parsed.group(j)) for j in range(1, 5)]
                    for _bboxes_parsed in location
                ]

                bbox = self.processor.post_processor.box_quantizer.dequantize(
                    boxes=torch.tensor(bbox_bins), size=image_size
                ).tolist()[0]

                click_point = (sum([bbox[0], bbox[2]]) / 2, sum([bbox[1], bbox[3]]) / 2)

                result["click_point"] = bbox if return_bbox else click_point
            else:
                result["click_point"] = [0, 0, 0, 0] if return_bbox else (0, 0)

        except Exception:
            result["click_point"] = [0, 0, 0, 0] if return_bbox else (0, 0)

        return result

    def _post_process_generation_point(self, text: str, image_size: tuple[int]):
        """Function that decodes model's generation into action json.

        Args:
            text: single generated sample
            image_size: corresponding image size
        """
        pattern = r"</s><s>(<[^>]+>|[^<\s]+)\s*([^<]*?)(<loc_\d+>.*)"
        point_pattern = r"<loc_(\d+)><loc_(\d+)>"
        match = re.search(pattern, text)

        if not match or (action := match.group(1)) not in self.ACTIONS:
            return {
                "action": "none",
                "type_text": None,
                "click_point": (0, 0),
            }

        type_text = match.group(2).strip() if match.group(2) else ""

        result = {
            "action": action,
            "type_text": type_text.strip() if type_text else None,
        }

        try:
            location = re.findall(point_pattern, text)[0]
            if len(location) > 0:
                bbox_bins = [int(loc) for loc in location]

                point = self.processor.post_processor.box_quantizer.dequantize(
                    boxes=torch.tensor(bbox_bins).repeat(2), size=image_size
                ).tolist()[:2]

                result["click_point"] = point
            else:
                result["click_point"] = (0, 0)

        except Exception:
            result["click_point"] = (0, 0)

        return result