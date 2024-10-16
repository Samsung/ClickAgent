import os

import albumentations as A
import cv2
import torch
import torch.nn.functional as F
from torch.utils.data import Dataset
from tqdm import tqdm


def padded_vstack(tensors, side="right", mode="constant", value=0):
    full_size = max([x.size(-1) for x in tensors])

    def make_padding(pad):
        if side == "left":
            return pad, 0
        elif side == "right":
            return 0, pad
        else:
            raise ValueError(f"side for padding '{side}' is unknown")

    out = torch.vstack(
        [
            (
                F.pad(x, make_padding(full_size - x.size(-1)), mode=mode, value=value)
                if full_size - x.size(-1) > 0
                else x
            )
            for x in tensors
        ],
    )
    return out


def collator(batch, pad_token_id):
    new_batch = {}
    for item in batch:

        for key, value in item.items():
            new_batch[key] = new_batch.get(key, []) + [value]

    padding_value = {"input_ids": pad_token_id, "labels": -100, "attention_mask": 0}

    for key, pad_value in padding_value.items():
        if key not in new_batch:
            continue

        new_batch[key] = padded_vstack(
            new_batch[key],
            value=pad_value,
            side="right",
        )

    new_batch["pixel_values"] = torch.stack(new_batch["pixel_values"])

    return new_batch


class FlorenceDataset(Dataset):
    def __init__(
            self,
            metadata,
            processor,
            img_root,
            load_images_to_memory=False,
            mode="train",
            image_size=(768, 768),
            transforms=None,
            aspect_ratio_resizing=False,
            lowercase=False,
    ):
        super().__init__()

        assert mode in [
            "train",
            "valid",
            "inference",
        ], 'mode not in ["train", "valid", "inference"]'
        self.load_images_to_memory = load_images_to_memory

        self.mode = mode
        self.metadata = metadata
        self.img_root = img_root
        self.lowercase = lowercase
        self.processor = processor

        self.target_w, self.target_h = image_size
        self.image_transforms = A.Compose([A.Resize(*image_size)])
        assert self.target_w == self.target_h, "Only MxM images are supported"

        resizing = (
            A.LongestMaxSize(max_size=min(image_size))
            if aspect_ratio_resizing
            else A.Resize(*image_size)
        )
        self.transforms = A.Compose(
            [resizing],
            bbox_params=A.BboxParams(
                format="pascal_voc", label_fields=["class_labels"]
            ),
        )

        if transforms is not None and isinstance(transforms, list):
            self.transforms.transforms = transforms + self.transforms.transforms
            self.image_transforms = transforms + self.image_transforms.transforms

        self.transforms.transforms.append(
            A.PadIfNeeded(
                min_height=self.target_h,
                min_width=self.target_w,
                position="center" if self.mode == "inference" else "random",
                border_mode=0,
                value=0,
                p=1.0,
            )
        )

        self.__action_type_value_mapper = {"swipe": "direction", "type": "typing"}

        if self.load_images_to_memory:
            image_names = list(set([sample["image"] for sample in self.metadata]))
            self.images_dict = {
                image_name: cv2.imread(str(os.path.join(self.img_root, image_name)))
                for image_name in tqdm(image_names, desc="Loading images...")
            }

    def _get_image_from_item(self, item):
        if self.load_images_to_memory:
            return self.images_dict[item["image"]]
        return cv2.cvtColor(
            cv2.imdecode(item["image"], cv2.IMREAD_ANYCOLOR), cv2.COLOR_BGR2RGB
        )

    def transform_image_and_annotations(self, image, target_bbox):
        if target_bbox is not None:
            bboxes = target_bbox if isinstance(target_bbox[0], list) else [target_bbox]
            transformed = self.transforms(
                image=image,
                bboxes=bboxes,
                class_labels=[0 for _ in bboxes],
            )
            target_bboxes = []
            target_bboxes_loc = []
            for bbox in transformed["bboxes"]:
                xmin, ymin, xmax, ymax = bbox

                xmin_loc = int(xmin / self.target_w * 1000)
                xmax_loc = int(xmax / self.target_w * 1000)
                ymin_loc = int(ymin / self.target_h * 1000)
                ymax_loc = int(ymax / self.target_h * 1000)
                target_bboxes.append([xmin, ymin, xmax, ymax])
                target_bboxes_loc.append([xmin_loc, ymin_loc, xmax_loc, ymax_loc])
        else:
            transformed = self.image_transforms
            target_bboxes = None
            target_bboxes_loc = None

        image = transformed["image"]

        return {
            "image": image,
            "target_bboxes": target_bboxes,
            "target_bboxes_loc_tokens": target_bboxes_loc,
        }

    def _get_output_text(self, item, output_bboxes):
        task = item.get("task", "<AGENT_ACTION>")
        if task == "<SCREEN_CAPTION>":
            return item["caption"]

        elif task == "<ELEMENT_CAPTION>":
            return item["purpose"]

        elif task == "<OD>":
            output = ""
            for box, name in zip(output_bboxes, item["names"]):
                xmin_loc, ymin_loc, xmax_loc, ymax_loc = box
                output += f"{name} <loc_{xmin_loc}><loc_{ymin_loc}><loc_{xmax_loc}><loc_{ymax_loc}> "
            return output

        elif task == "<AGENT_ACTION>":
            xmin_loc, ymin_loc, xmax_loc, ymax_loc = output_bboxes[0]

            location_suffix = (
                f"<loc_{xmin_loc}><loc_{ymin_loc}><loc_{xmax_loc}><loc_{ymax_loc}>"
            )

            if (action_type := item["action_type"]) in self.__action_type_value_mapper:
                return f"{action_type} {item[self.__action_type_value_mapper[action_type]]} {location_suffix}"
            return f"{action_type} {location_suffix}"

    def _get_input_text(self, item, input_bboxes=None):
        task = item.get("task", "<AGENT_ACTION>")
        input_text = task
        if task != "<OD>":
            if task == "<ELEMENT_CAPTION>":
                xmin_loc, ymin_loc, xmax_loc, ymax_loc = input_bboxes[0]
                location = (
                    f"<loc_{xmin_loc}><loc_{ymin_loc}><loc_{xmax_loc}><loc_{ymax_loc}>"
                )
                input_text += f"What is the purpose of the element {location}"
            else:
                input_text += " " + (
                    item["generated_command"].lower()
                    if self.lowercase
                    else item["generated_command"]
                )

        return input_text

    def __len__(self):
        return len(self.metadata)

    def __getitem__(self, idx):
        item = self.metadata[idx]
        image = self._get_image_from_item(item)

        self.metadata[idx]["original_image_shape"] = image.shape

        bboxes = item.get("target_bbox", [])
        # for backward compatibility, if "target_bbox" is not a list of bboxes then wrap it into a list
        if bboxes and not isinstance(bboxes[0], list):
            bboxes = [bboxes]

        # prepend bboxes list with coordinates of the whole image bbox
        bboxes = [[0, 0, *image.shape[1::-1]]] + bboxes

        transformed_image_and_annotations = self.transform_image_and_annotations(
            image=image, target_bbox=bboxes
        )
        self.metadata[idx]["original_image_location"] = transformed_image_and_annotations["target_bboxes"][0]

        # strip whole image bbox
        transformed_image_and_annotations["target_bboxes"] = transformed_image_and_annotations["target_bboxes"][1:]
        transformed_image_and_annotations["target_bboxes_loc_tokens"] = transformed_image_and_annotations[
                                                                            "target_bboxes_loc_tokens"][1:]

        image = transformed_image_and_annotations["image"]

        target_bboxes_loc_tokens = (
            transformed_image_and_annotations["target_bboxes_loc_tokens"]
            if self.mode in ["train", "valid"]
            else None
        )
        input_text = self._get_input_text(
            item=item, input_bboxes=target_bboxes_loc_tokens
        )

        encoding = self.processor(
            images=image,
            text=input_text,
            return_tensors="pt",
            do_resize=False,
        )

        if self.mode in ["train", "valid"]:
            output_text = self._get_output_text(
                item=item,
                output_bboxes=transformed_image_and_annotations[
                    "target_bboxes_loc_tokens"
                ],
            )
            if self.lowercase:
                output_text = output_text.lower()

            encoding["labels"] = self.processor.tokenizer(
                text=output_text, return_tensors="pt"
            ).input_ids

        if self.mode == "valid":
            encoding["action_type"] = item["action_type"]
            encoding["type_text"] = item.get("typing", None)

            if encoding["type_text"] is not None and self.lowercase:
                encoding["type_text"] = encoding["type_text"].lower()

            encoding["image_size"] = (self.target_h, self.target_w)
            encoding["target_bbox"] = transformed_image_and_annotations[
                "target_bboxes"
            ][0]

        if self.mode == "inference":
            encoding["image_size"] = (self.target_h, self.target_w)

        encoding = {
            k: (
                v.squeeze()
                if k not in ["target_bbox", "image_size", "action_type", "type_text"]
                else v
            )
            for k, v in encoding.items()
        }

        if self.mode == "inference":
            needs_box_click = item.get("needs_box_click", True)
            encoding["needs_box_click"] = True if needs_box_click is None else needs_box_click

        return encoding
