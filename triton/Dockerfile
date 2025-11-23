# Triton Inference Server with OPUS-MT Models
# This Dockerfile packages the model repository into the Triton image for deployment to Kubernetes

FROM nvcr.io/nvidia/tritonserver:24.11-py3

# Set working directory
WORKDIR /models

# Copy the entire model repository into the image
# This includes all OPUS-MT model directories with their config.pbtxt and model.onnx files
COPY model-repository /models

# Set proper permissions
RUN chmod -R 755 /models

# Expose Triton ports
EXPOSE 8000 8001 8002

# Start Triton with the embedded model repository
# - model-repository: Path to models
# - strict-model-config: Allow models without config files
# - log-verbose: Enable detailed logging
# - model-control-mode: poll for dynamic model loading
# - allow-http: Enable HTTP endpoint
# - strict-readiness: Don't require all models loaded for readiness
ENTRYPOINT ["tritonserver", \
            "--model-repository=/models", \
            "--strict-model-config=false", \
            "--log-verbose=1", \
            "--model-control-mode=poll", \
            "--allow-http=true", \
            "--strict-readiness=false"]
