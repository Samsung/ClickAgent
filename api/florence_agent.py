from base_agent import BaseAgent


class FlorenceAgent(BaseAgent):
    """
    Agent class specifically for Florence-2 usage.
    """

    def __init__(
        self, base_model: str, device: str = "cuda", prediction_format="box"
    ) -> None:
        super(FlorenceAgent, self).__init__(
            base_model, device=device, prediction_format=prediction_format
        )

    def freeze_vision_encoder(self):
        for param in self.model.vision_tower.parameters():
            param.requires_grad = False

    def freeze_language_encoder(self):
        for param in self.model.language_model.model.shared.parameters():
            param.requires_grad = False
        for param in self.model.language_model.model.encoder.parameters():
            param.requires_grad = False

    def freeze_decoder(self):
        for param in self.model.language_model.model.decoder.parameters():
            param.requires_grad = False

    def unfreeze_vision_encoder(self):
        for param in self.model.vision_tower.parameters():
            param.requires_grad = True

    def unfreeze_language_encoder(self):
        for param in self.model.language_model.model.shared.parameters():
            param.requires_grad = True
        for param in self.model.language_model.model.encoder.parameters():
            param.requires_grad = True

    def unfreeze_decoder(self):
        for param in self.model.language_model.model.decoder.parameters():
            param.requires_grad = True

    def get_vision_enc_grad_norm(self):
        total_norm = 0
        for p in self.model.vision_tower.parameters():
            if p.requires_grad:
                param_norm = p.grad.detach().data.norm(2)
                total_norm += param_norm.item() ** 2
        total_norm = total_norm**0.5
        return total_norm

    def get_lang_enc_grad_norm(self):
        total_norm = 0
        for p in self.model.language_model.model.encoder.parameters():
            if p.requires_grad:
                param_norm = p.grad.detach().data.norm(2)
                total_norm += param_norm.item() ** 2
        total_norm = total_norm**0.5
        return total_norm

    def predict(
        self, batch: dict, image_sizes: list, return_bbox: bool = False, **kwargs
    ):
        """Predicts captions and bounding boxes of given batch.

        Args:
            return_bbox: specify if the returned should be bbox (4 elements) or point (2 elements)
        """
        outputs = self.model.generate(**batch, **kwargs)
        generated_texts = self.processor.batch_decode(
            outputs, skip_special_tokens=False
        )
        predictions = [
            (
                self._post_process_generation_box(text, image_size, return_bbox)
                if self.prediction_format == "box"
                else self._post_process_generation_point(text, image_size)
            )
            for text, image_size in zip(generated_texts, image_sizes)
        ]
        return predictions

    def get_bboxes_from_predictions(self, predictions: dict):
        """Extracts and returns list of bboxes from pred dicts."""
        bboxes = []
        for pred in predictions:
            try:
                bboxes.append([int(xy) for xy in pred["click_point"]])
            except Exception:
                bboxes.append([0, 0, 0, 0])
        return bboxes