import os


def build_client():
    from openai import OpenAI

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    return OpenAI(api_key=api_key, base_url=base_url)
