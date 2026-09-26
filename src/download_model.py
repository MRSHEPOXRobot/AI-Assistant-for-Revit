from huggingface_hub import hf_hub_download

REPO_ID = "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF"
FILENAME = "qwen2.5-coder-14b-instruct-q5_k_m.gguf"

if __name__ == "__main__":
    path = hf_hub_download(repo_id=REPO_ID, filename=FILENAME)
    print(f"Model Path: {path}")
