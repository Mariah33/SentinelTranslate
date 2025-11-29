NLLB-200-distilled-600M Model Configuration
============================================

Place ONNX model at: 1/model.onnx

Model Source:
-------------
facebook/nllb-200-distilled-600M from Hugging Face
https://huggingface.co/facebook/nllb-200-distilled-600M

Export to ONNX:
---------------
The model should be exported to ONNX format with embedded preprocessing
that handles FLORES-200 language codes. The ONNX model should accept
INPUT_TEXT (string) and return OUTPUT_TEXT (string).

Language Codes:
---------------
NLLB uses FLORES-200 language codes (e.g., "fra_Latn", "eng_Latn", "deu_Latn").
The sidecar will handle conversion from ISO 639-1 codes to FLORES-200 format.

Input Format:
-------------
The input text should be prefixed with source language code:
Example: "fra_Latn Hello world" for French to English translation

Alternative: Python Backend
----------------------------
For more advanced preprocessing, you can switch to a Python backend:
1. Change config.pbtxt platform to "python"
2. Create model.py in 1/ directory with preprocessing logic
3. Handle tokenization, language code embedding, and detokenization

Model Size:
-----------
~600M parameters (~1.2GB ONNX file)
