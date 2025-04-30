# app/utils/summarizer.py
import logging
from typing import List, Dict, Any
from pathlib import Path # Import Path

# Import Document model from models.py
from ..models import Document # Import your DB model
# Import settings for configuration (e.g., LLM URL, summary length)
from ..config import settings
# Import httpx for making asynchronous HTTP requests
import httpx

logger = logging.getLogger(__name__)

# --- LLM Initialization (using Ollama) ---
# This is similar to the RAG handler, can potentially share initialization
def get_llm_url() -> str:
    """Gets the base URL for the LLM (Ollama)."""
    # Ensure this matches the setting in your config.yaml/config.py
    return settings.ollama.base_url

# --- Summarization Function ---

async def generate_summary(text_content: str, output_format: str = "txt") -> Dict[str, Any]:
    """
    Generates a summary of the given text content using the LLM.
    Optionally formats the output based on the specified format.
    """
    logger.info(f"Generating summary for text content (length: {len(text_content)}) in format: {output_format}")

    if not text_content.strip():
        logger.warning("Attempted to generate summary for empty text content.")
        return {"summary": "No content to summarize."}

    # Define the prompt for the LLM
    # You can adjust this prompt based on your desired summary style and length
    prompt = f"""Summarize the following text.

    <text>
    {text_content}
    </text>

    Provide the summary in {output_format} format.
    Summary:""" # Basic prompt, refine as needed


    # You might need to adjust the max tokens or other parameters based on the LLM and desired summary length
    max_tokens = settings.summary.summary_max_length # Use setting for max length

    try:
        llm_url = f"{get_llm_url()}/api/generate" # Adjust endpoint if necessary
        async with httpx.AsyncClient() as client:
            # Parameters for the Ollama generate API
            payload = {
                "prompt": prompt,
                "stream": False, # Do not stream the response for summary task
                "options": {
                    "num_predict": max_tokens, # Limit the length of the summary
                    # Add other Ollama options as needed (e.g., temperature, top_p)
                }
            }
            logger.debug(f"Sending summary request to LLM: {payload}")

            response = await client.post(llm_url, json=payload, timeout=600) # Increased timeout for summary
            response.raise_for_status() # Raise an exception for bad status codes

            ollama_response_data = response.json()
            summary_text = ollama_response_data.get("response", "").strip()

        logger.info(f"LLM summary generation successful. Summary length: {len(summary_text)}")

        # --- Format the summary based on output_format ---
        formatted_summary = summary_text

        # Basic formatting examples (more sophisticated formatting would be needed for docx, script)
        if output_format == "script":
            # Basic script formatting: maybe add speaker labels or scene breaks
            formatted_summary = f"## Summary Script\n\n{summary_text}" # Simple example

        # Add formatting for other types (docx, audio) here if not handled by LLM directly

        # If output_format is audio, the summary_text should be the text to be spoken
        # The actual TTS generation happens in the generate_summary_task in tasks.py
        # This function just returns the text content that *will be* spoken.
        if output_format == "audio":
            # For audio, the 'summary' key should contain the text for TTS
            return {"summary": summary_text, "format": "text_for_tts"} # Indicate it's text for TTS

        # Return the generated and formatted summary
        return {"summary": formatted_summary, "format": output_format}


    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error communicating with LLM for summary: {e.response.status_code} - {e.response.text}")
        return {"summary": f"Error from LLM ({e.response.status_code}): {e.response.text}", "format": "txt"}
    except httpx.RequestError as e:
        logger.error(f"Request error communicating with LLM for summary: {e}")
        return {"summary": f"Error communicating with LLM: {e}", "format": "txt"}
    except Exception as e:
        logger.error(f"An unexpected error occurred during summary generation: {e}", exc_info=True)
        return {"summary": f"An unexpected error occurred during summary generation: {e}", "format": "txt"}

# --- Text-to-Speech (TTS) Function (Placeholder) ---
# This function would be called by the generate_summary_task if output_format is "audio"
# It needs to be implemented based on the chosen TTS library/service.

async def generate_audio_from_text(text_content: str, output_path: Path) -> None:
    """
    Generates an audio file from text content using a TTS engine. (Placeholder)
    """
    logger.info(f"Attempting to generate audio from text (length: {len(text_content)}) to {output_path}")
    # Ensure the output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # --- TTS Implementation ---
    # This section needs to be replaced with actual TTS code
    # based on settings.summary.tts_engine (e.g., Coqui TTS, Bark, etc.)

    tts_engine = settings.summary.tts_engine
    if tts_engine == "coqui_tts":
        try:
            from TTS.api import TTS
            # Assuming you have a TTS model downloaded
            # The model_name should come from settings (e.g., settings.summary.tts_model_name)
            # And speaker settings if applicable (settings.summary.tts_speaker)
            logger.warning("Coqui TTS generation not fully implemented. Using placeholder.")
            # Example (requires model download):
            # tts = TTS(model_name=settings.summary.tts_model_name, progress_bar=False, gpu=False) # Adjust gpu based on available hardware
            # # Example for a multi-speaker model like VCTK
            # # speaker = settings.summary.tts_speaker_1 # Get speaker from settings
            # # tts.tts_to_file(text=text_content, speaker=speaker, file_path=output_path)
            # # Create a dummy file for now
            # with open(output_path, 'w') as f:
            #      f.write("placeholder audio data") # Write some placeholder content
            # logger.info(f"Placeholder audio file created at {output_path}")

            raise NotImplementedError("Coqui TTS implementation is a placeholder.")


        except ImportError:
            logger.error("Coqui TTS library not found. Install it: pip install TTS")
            raise ImportError("Coqui TTS library not found.")
        except Exception as e:
             logger.error(f"Error during Coqui TTS generation: {e}")
             raise RuntimeError(f"Coqui TTS generation failed: {e}") from e

    elif tts_engine == "bark":
         logger.warning("Bark TTS generation not fully implemented.")
         raise NotImplementedError("Bark TTS implementation is a placeholder.")

    elif tts_engine == "none" or not tts_engine:
        logger.warning("TTS engine is set to 'none' or not configured. Cannot generate audio.")
        raise NotImplementedError("TTS engine not configured.")

    else:
        logger.error(f"Unknown TTS engine specified in settings: {tts_engine}")
        raise ValueError(f"Unknown TTS engine: {tts_engine}")

    # --- End of TTS Implementation ---

    logger.info(f"Audio generation task finished for {output_path}")
