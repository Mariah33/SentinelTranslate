"""
Example usage of the SentinelTranslate Frontend API for batch S3 parquet translation.
"""

import time

import requests

# Configuration
FRONTEND_URL = "http://localhost:8090"


# Example 1: Submit a batch translation job
def submit_batch_job():
    """Submit a batch translation job from S3 parquet file."""
    payload = {
        "s3_bucket": "my-translation-bucket",
        "s3_key": "input/french_documents.parquet",
        "text_column": "content",  # Column containing text to translate
        "source_lang": "fr",  # French
        "target_lang": "en",  # English
        "output_s3_bucket": "my-translation-bucket",  # Optional, defaults to input bucket
        "output_s3_key": "output/french_documents_en.parquet",  # Optional
        "id_column": "document_id",  # Optional, preserves ID column
    }

    response = requests.post(f"{FRONTEND_URL}/batch/translate", json=payload)
    response.raise_for_status()

    result = response.json()
    print("✅ Job submitted successfully!")
    print(f"   Job ID: {result['job_id']}")
    print(f"   Message: {result['message']}")
    return result["job_id"]


# Example 2: Check job status
def check_job_status(job_id: str):
    """Check the status of a batch translation job."""
    response = requests.get(f"{FRONTEND_URL}/batch/status/{job_id}")
    response.raise_for_status()

    status = response.json()
    print(f"\n📊 Job Status: {status['status']}")

    if status["status"] == "SUCCESS":
        result = status["result"]
        print("   ✅ Translation completed!")
        print(f"   Output location: {result['output_location']}")
        print(f"   Total rows: {result['total_rows']}")
        print(f"   Successful: {result['successful_translations']}")
        print(f"   Failed: {result['failed_rows']}")
        if result["failed_indices"]:
            print(f"   Failed row indices: {result['failed_indices']}")

    elif status["status"] == "FAILURE":
        print(f"   ❌ Job failed: {status['error']}")

    elif status["status"] == "PROGRESS":
        print("   ⏳ Job in progress...")

    else:
        print("   ⏸️  Job pending...")

    return status


# Example 3: Poll until completion
def poll_until_complete(job_id: str, poll_interval: int = 5):
    """Poll job status until completion (success or failure)."""
    print(f"\n⏳ Polling job {job_id} every {poll_interval} seconds...")

    while True:
        status = check_job_status(job_id)

        if status["status"] in ["SUCCESS", "FAILURE"]:
            break

        time.sleep(poll_interval)

    return status


# Example 4: Full workflow
def full_workflow_example():
    """Complete example: submit job and wait for completion."""
    print("=" * 60)
    print("SentinelTranslate Frontend API - Full Workflow Example")
    print("=" * 60)

    # Step 1: Submit job
    job_id = submit_batch_job()

    # Step 2: Poll until complete
    final_status = poll_until_complete(job_id, poll_interval=5)

    # Step 3: Print final result
    print("\n" + "=" * 60)
    if final_status["status"] == "SUCCESS":
        print("🎉 Translation completed successfully!")
        print(f"Download your results from: {final_status['result']['output_location']}")
    else:
        print("❌ Translation failed!")
        print(f"Error: {final_status['error']}")
    print("=" * 60)


if __name__ == "__main__":
    # Run the full workflow example
    full_workflow_example()

    # Or run individual examples:
    # job_id = submit_batch_job()
    # check_job_status(job_id)
