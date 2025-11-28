import tritonclient.http as http


class TritonClient:
    """Client for NVIDIA Triton Inference Server.

    Supports both OPUS-MT and NLLB-200 translation models.
    """

    def __init__(self, url):
        self.client = http.InferenceServerClient(url=url)

    def translate(self, model: str, text: str, src_lang: str | None = None, tgt_lang: str | None = None) -> str:
        """Translate text using specified Triton model.

        Args:
            model: Triton model name (e.g., "opus-mt-fr-en" or "nllb-200-distilled-600m")
            text: Source text to translate
            src_lang: Source language code in FLORES-200 format (required for NLLB)
            tgt_lang: Target language code in FLORES-200 format (required for NLLB)

        Returns:
            Translated text

        Notes:
            - For OPUS-MT models: language info embedded in model name
            - For NLLB models: prepends src_lang to text and appends tgt_lang marker
        """
        # Format input based on model type
        if "nllb" in model.lower():
            # NLLB format: prepend source language code
            # The ONNX model should handle the language code prefix
            if not src_lang or not tgt_lang:
                raise ValueError("NLLB models require src_lang and tgt_lang parameters")
            formatted_text = f"{src_lang} {text}"
        else:
            # OPUS-MT format: plain text (language specified in model name)
            formatted_text = text

        # Prepare Triton inference request
        inp = http.InferInput("INPUT_TEXT", [1], "BYTES")
        inp.set_data_from_numpy([formatted_text.encode("utf-8")])
        out = http.InferRequestedOutput("OUTPUT_TEXT")

        # Execute inference
        res = self.client.infer(model, inputs=[inp], outputs=[out])

        return res.as_numpy("OUTPUT_TEXT")[0].decode("utf-8")
