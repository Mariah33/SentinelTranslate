import numpy as np
import tritonclient.http as http


class TritonClient:
    def __init__(self, url):
        self.client = http.InferenceServerClient(url=url)

    def forward(self, model, text):
        inp = http.InferInput("INPUT_TEXT", [1], "BYTES")
        inp.set_data_from_numpy(np.array([text.encode("utf-8")], dtype=object))
        out = http.InferRequestedOutput("OUTPUT_TEXT")
        res = self.client.infer(model, inputs=[inp], outputs=[out])
        return res.as_numpy("OUTPUT_TEXT")[0].decode("utf-8")
