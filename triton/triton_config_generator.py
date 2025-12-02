#!/usr/bin/env python3
"""
Triton Config Generator

Automatically generates config.pbtxt files for ONNX models in Triton model repository.
Supports both OPUS-MT and NLLB-200 model architectures.

Usage:
    # Generate configs for all models in directory
    python triton_config_generator.py --model-dir model-repository/

    # Generate config for specific model
    python triton_config_generator.py --model-name opus-mt-fr-en --model-dir model-repository/

    # Custom batch size and instance count
    python triton_config_generator.py --model-dir model-repository/ --max-batch-size 16 --instance-count 2
"""

import argparse
import logging
from pathlib import Path
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def generate_opus_mt_config(
    model_name: str,
    max_batch_size: int = 8,
    instance_count: int = 1,
    device_kind: str = "KIND_CPU",
) -> str:
    """
    Generate Triton config.pbtxt for OPUS-MT ONNX model.

    Args:
        model_name: Model name (e.g., 'opus-mt-fr-en')
        max_batch_size: Maximum batch size for inference
        instance_count: Number of model instances to run
        device_kind: Device type ('KIND_CPU' or 'KIND_GPU')

    Returns:
        config.pbtxt content as string
    """
    return f'''name: "{model_name}"
backend: "onnxruntime"
max_batch_size: {max_batch_size}

# Input tensor: tokenized text
input [
  {{
    name: "input_ids"
    data_type: TYPE_INT64
    dims: [-1]
  }},
  {{
    name: "attention_mask"
    data_type: TYPE_INT64
    dims: [-1]
  }}
]

# Output tensor: translated token IDs
output [
  {{
    name: "sequences"
    data_type: TYPE_INT64
    dims: [-1]
  }}
]

# Model instance configuration
instance_group [
  {{
    count: {instance_count}
    kind: {device_kind}
  }}
]

# ONNX Runtime optimization
optimization {{
  execution_accelerators {{
    cpu_execution_accelerator : [ {{
      name : "onnxruntime"
    }}]
  }}
}}

# Dynamic batching for better throughput
dynamic_batching {{
  preferred_batch_size: [1, 2, 4, 8]
  max_queue_delay_microseconds: 100
}}

# Model versioning
version_policy {{
  latest {{
    num_versions: 1
  }}
}}
'''


def generate_nllb_config(
    model_name: str = "nllb-200-distilled-600m",
    max_batch_size: int = 8,
    instance_count: int = 1,
    device_kind: str = "KIND_CPU",
) -> str:
    """
    Generate Triton config.pbtxt for NLLB-200 ONNX model.

    Args:
        model_name: Model name (default: 'nllb-200-distilled-600m')
        max_batch_size: Maximum batch size for inference
        instance_count: Number of model instances to run
        device_kind: Device type ('KIND_CPU' or 'KIND_GPU')

    Returns:
        config.pbtxt content as string
    """
    return f'''name: "{model_name}"
backend: "onnxruntime"
max_batch_size: {max_batch_size}

# Input tensors: tokenized text with language codes
input [
  {{
    name: "input_ids"
    data_type: TYPE_INT64
    dims: [-1]
  }},
  {{
    name: "attention_mask"
    data_type: TYPE_INT64
    dims: [-1]
  }},
  {{
    name: "forced_bos_token_id"
    data_type: TYPE_INT64
    dims: [1]
    optional: true
  }}
]

# Output tensor: translated token IDs
output [
  {{
    name: "sequences"
    data_type: TYPE_INT64
    dims: [-1]
  }}
]

# Model instance configuration
instance_group [
  {{
    count: {instance_count}
    kind: {device_kind}
  }}
]

# ONNX Runtime optimization
optimization {{
  execution_accelerators {{
    cpu_execution_accelerator : [ {{
      name : "onnxruntime"
    }}]
  }}
}}

# Dynamic batching for better throughput
dynamic_batching {{
  preferred_batch_size: [1, 2, 4, 8]
  max_queue_delay_microseconds: 100
}}

# Model versioning
version_policy {{
  latest {{
    num_versions: 1
  }}
}}
'''


def detect_model_type(model_dir: Path) -> str:
    """
    Detect model type based on directory name.

    Args:
        model_dir: Path to model directory

    Returns:
        Model type ('opus-mt' or 'nllb')
    """
    model_name = model_dir.name

    if model_name.startswith("opus-mt-"):
        return "opus-mt"
    elif "nllb" in model_name.lower():
        return "nllb"
    else:
        logger.warning(f"Unknown model type for {model_name}, assuming OPUS-MT")
        return "opus-mt"


def generate_config_for_model(
    model_dir: Path,
    max_batch_size: int = 8,
    instance_count: int = 1,
    device_kind: str = "KIND_CPU",
    force: bool = False,
) -> bool:
    """
    Generate config.pbtxt for a single model.

    Args:
        model_dir: Path to model directory (e.g., model-repository/opus-mt-fr-en/)
        max_batch_size: Maximum batch size
        instance_count: Number of model instances
        device_kind: Device type
        force: Overwrite existing config.pbtxt

    Returns:
        True if config was generated, False otherwise
    """
    config_path = model_dir / "config.pbtxt"

    # Check if config already exists
    if config_path.exists() and not force:
        logger.info(f"✓ Skipping {model_dir.name} (config.pbtxt already exists)")
        return False

    # Detect model type
    model_type = detect_model_type(model_dir)
    model_name = model_dir.name

    # Generate appropriate config
    if model_type == "opus-mt":
        config_content = generate_opus_mt_config(
            model_name=model_name,
            max_batch_size=max_batch_size,
            instance_count=instance_count,
            device_kind=device_kind,
        )
    else:  # nllb
        config_content = generate_nllb_config(
            model_name=model_name,
            max_batch_size=max_batch_size,
            instance_count=instance_count,
            device_kind=device_kind,
        )

    # Write config file
    config_path.write_text(config_content)
    logger.info(f"✓ Generated config for {model_name} [{model_type}]")
    return True


def generate_configs_for_repository(
    model_repo_dir: Path,
    max_batch_size: int = 8,
    instance_count: int = 1,
    device_kind: str = "KIND_CPU",
    force: bool = False,
) -> tuple[int, int]:
    """
    Generate config.pbtxt files for all models in repository.

    Args:
        model_repo_dir: Path to model repository root
        max_batch_size: Maximum batch size
        instance_count: Number of model instances
        device_kind: Device type
        force: Overwrite existing configs

    Returns:
        Tuple of (generated_count, skipped_count)
    """
    if not model_repo_dir.exists():
        logger.error(f"Model repository not found: {model_repo_dir}")
        return (0, 0)

    generated = 0
    skipped = 0

    # Find all model directories (contain a version subdirectory like "1/")
    model_dirs = []
    for item in model_repo_dir.iterdir():
        if item.is_dir():
            version_dir = item / "1"
            if version_dir.exists():
                model_dirs.append(item)

    if not model_dirs:
        logger.warning(f"No model directories found in {model_repo_dir}")
        return (0, 0)

    logger.info(f"Found {len(model_dirs)} model directories")

    for model_dir in sorted(model_dirs):
        was_generated = generate_config_for_model(
            model_dir=model_dir,
            max_batch_size=max_batch_size,
            instance_count=instance_count,
            device_kind=device_kind,
            force=force,
        )

        if was_generated:
            generated += 1
        else:
            skipped += 1

    return (generated, skipped)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate Triton config.pbtxt files for ONNX models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate configs for all models
  python triton_config_generator.py --model-dir model-repository/

  # Generate config for specific model
  python triton_config_generator.py --model-name opus-mt-fr-en --model-dir model-repository/

  # GPU deployment with larger batches
  python triton_config_generator.py --model-dir model-repository/ \\
      --max-batch-size 32 --device-kind KIND_GPU --instance-count 2

  # Force regenerate all configs
  python triton_config_generator.py --model-dir model-repository/ --force
        """,
    )

    parser.add_argument(
        "--model-dir",
        type=Path,
        required=True,
        help="Path to model repository directory",
    )

    parser.add_argument(
        "--model-name",
        type=str,
        help="Generate config for specific model only (e.g., 'opus-mt-fr-en')",
    )

    parser.add_argument(
        "--max-batch-size",
        type=int,
        default=8,
        help="Maximum batch size for inference (default: 8)",
    )

    parser.add_argument(
        "--instance-count",
        type=int,
        default=1,
        help="Number of model instances per device (default: 1)",
    )

    parser.add_argument(
        "--device-kind",
        type=str,
        choices=["KIND_CPU", "KIND_GPU"],
        default="KIND_CPU",
        help="Device type for inference (default: KIND_CPU)",
    )

    parser.add_argument(
        "--backend",
        type=str,
        default="onnxruntime",
        help="Triton backend (default: onnxruntime)",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing config.pbtxt files",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Generate config for specific model
    if args.model_name:
        model_dir = args.model_dir / args.model_name

        if not model_dir.exists():
            logger.error(f"Model directory not found: {model_dir}")
            exit(1)

        was_generated = generate_config_for_model(
            model_dir=model_dir,
            max_batch_size=args.max_batch_size,
            instance_count=args.instance_count,
            device_kind=args.device_kind,
            force=args.force,
        )

        if was_generated:
            logger.info(f"✓ Config generated at {model_dir / 'config.pbtxt'}")
        else:
            logger.info(f"Config already exists at {model_dir / 'config.pbtxt'}")

    # Generate configs for entire repository
    else:
        generated, skipped = generate_configs_for_repository(
            model_repo_dir=args.model_dir,
            max_batch_size=args.max_batch_size,
            instance_count=args.instance_count,
            device_kind=args.device_kind,
            force=args.force,
        )

        print("\n" + "=" * 70)
        print("CONFIG GENERATION SUMMARY")
        print("=" * 70)
        print(f"Generated:  {generated} ✓")
        print(f"Skipped:    {skipped}")
        print(f"Total:      {generated + skipped}")
        print("=" * 70)
        print()


if __name__ == "__main__":
    main()
