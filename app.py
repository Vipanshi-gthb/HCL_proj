"""Root application entry point for P_123 Conversational Data Analysis Assistant.

Compatible with both local execution and Hugging Face Spaces deployment.
Binds 0.0.0.0 and honours PORT / GRADIO_SERVER_PORT when running in cloud/container environments.
"""

import os
import sys
import gradio as gr

from src.config import get_settings
from src.ui import create_ui


def main():
    settings = get_settings()

    # Determine port and host binding
    port = int(os.getenv("PORT", os.getenv("GRADIO_SERVER_PORT", "7860")))
    is_space = bool(os.getenv("SPACE_ID"))
    has_explicit_port = bool(os.getenv("PORT"))

    server_name = "0.0.0.0" if (is_space or has_explicit_port) else "127.0.0.1"

    # Set stdout encoding for Windows console compatibility
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    # Startup diagnostics (NEVER prints secrets)
    status_str = "Configured" if settings.is_gemini_configured else "Not Configured (offline mode)"
    print("=" * 60, flush=True)
    print("P_123: Conversational Data Analysis Assistant", flush=True)
    print(f"Gradio version: {gr.__version__}", flush=True)
    print(f"AI Planner Status: {status_str}", flush=True)
    print(f"Gemini Model: {settings.gemini_model}", flush=True)
    print(f"Server Binding: http://{server_name}:{port}", flush=True)
    print("=" * 60, flush=True)

    demo = create_ui()
    demo.queue(max_size=20).launch(
        server_name=server_name,
        server_port=port,
        show_error=True,
    )


if __name__ == "__main__":
    main()
