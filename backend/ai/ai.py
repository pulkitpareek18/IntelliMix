import logging
import math
import os
import re
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types


LOGGER = logging.getLogger(__name__)


SYSTEM_INSTRUCTION = """
Request Analysis:

Carefully analyze the user's prompt to understand the requirements, including the number of songs, total duration, and any specific themes or transitions.

Clearly distinguish between two scenarios:

If the user specifies a fixed number of songs (e.g., "make a mix of 3 songs"), strictly use only that number of songs.

If the user specifies only a duration (e.g., "make a 5-minute parody"), you may use any number of songs to achieve the desired length.

Song Selection:

Search for high-quality or official versions of the specified songs on YouTube.

If no specific songs are mentioned, select popular songs that fit the described mood or theme.

Timestamp Identification:

Choose timestamps from each song that blend well together, maintaining a consistent vibe or theme.

Consider using impactful, catchy, or melodious parts of the songs to enhance the listening experience.

Flow and Transition:

Ensure smooth transitions between songs to create a cohesive and natural mix.

Maintain a consistent beat, rhythm, or musical theme throughout the parody.

Duration and Song Count Compliance:

Respect the user's specified requirements for the number of songs and minimum duration.

If the user wants a 5-minute parody with a fixed number of songs (e.g., 3 songs), use only those songs and adjust timestamps to meet the duration.

If the user wants a 5-minute parody without specifying the number of songs, freely use as many songs as needed to achieve the desired length.

Make sure the duration for all the songs is not equal for all the songs, keep it different on the basis of the song and the best part of the song to groove on.

Creative Flexibility:

Be flexible in mixing styles and transitions based on the genre or mood suggested by the user.

If the user specifies a genre, mood, or theme, adapt the song selection and mixing approach accordingly.

Human-Like Decision Making:

Behave as naturally and human-like as possible when curating the mix.

Make decisions as a professional DJ or music producer would, prioritizing the flow and musical coherence.

Output the result in the following JSON format only (without markdown fences):

{
  "mixTitle": "Descriptive title of the mix",
  "songs": [
    {
      "title": "Song Title",
      "artist": "Artist Name",
      "url": "YouTube URL",
      "startTime": "HH:MM:SS",
      "endTime": "HH:MM:SS"
    }
  ]
}
"""


class AIServiceError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 502,
        error_code: str = "AI_SERVICE_ERROR",
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.retry_after_seconds = retry_after_seconds


def _extract_status_code(exc: Exception) -> int:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    match = re.search(r"^\s*(\d{3})\b", str(exc))
    if match:
        return int(match.group(1))
    return 502


def _extract_retry_after_seconds(error_text: str) -> int | None:
    patterns = [
        r"retry in\s+([0-9]+(?:\.[0-9]+)?)s",
        r"retryDelay[\"']?\s*[:=]\s*[\"']([0-9]+(?:\.[0-9]+)?)s",
    ]
    for pattern in patterns:
        match = re.search(pattern, error_text, re.IGNORECASE)
        if not match:
            continue
        try:
            return max(1, int(math.ceil(float(match.group(1)))))
        except (TypeError, ValueError):
            continue
    return None


def _map_genai_error(exc: Exception, *, model_name: str) -> AIServiceError:
    status_code = _extract_status_code(exc)
    raw_error = str(exc)
    retry_after_seconds = _extract_retry_after_seconds(raw_error)

    if status_code == 404:
        return AIServiceError(
            f"Configured Gemini model '{model_name}' was not found. Update GEMINI_MODEL_NAME to a supported model.",
            status_code=502,
            error_code="AI_MODEL_NOT_FOUND",
        )

    if status_code == 429:
        return AIServiceError(
            f"Gemini quota or rate limit exceeded for model '{model_name}'. Retry later or use a billed Gemini project.",
            status_code=429,
            error_code="AI_RATE_LIMITED",
            retry_after_seconds=retry_after_seconds,
        )

    if status_code == 503:
        return AIServiceError(
            f"Gemini model '{model_name}' is temporarily unavailable due to high demand. Retry shortly.",
            status_code=503,
            error_code="AI_TEMPORARILY_UNAVAILABLE",
            retry_after_seconds=retry_after_seconds,
        )

    if status_code >= 500:
        return AIServiceError(
            "Gemini service returned an upstream error. Retry shortly.",
            status_code=502,
            error_code="AI_UPSTREAM_ERROR",
            retry_after_seconds=retry_after_seconds,
        )

    return AIServiceError(
        "Gemini request failed. Verify API key, model, and prompt, then retry.",
        status_code=502,
        error_code="AI_REQUEST_FAILED",
        retry_after_seconds=retry_after_seconds,
    )


def _read_int_env(name: str, default: int, *, minimum: int = 0) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        return max(minimum, int(raw_value))
    except (TypeError, ValueError):
        return default


def _read_float_env(name: str, default: float, *, minimum: float = 0.0) -> float:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        return max(minimum, float(raw_value))
    except (TypeError, ValueError):
        return default


def generate(prompt: str = "create a parody of honey singh songs", json_path: str = "audio_data.json") -> str:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise AIServiceError(
            "GOOGLE_API_KEY is not configured",
            status_code=500,
            error_code="AI_KEY_MISSING",
        )
    model_name = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
    max_retries = _read_int_env("GEMINI_MAX_RETRIES", 2, minimum=0)
    retry_base_seconds = _read_float_env("GEMINI_RETRY_BASE_SECONDS", 2.0, minimum=1.0)

    client = genai.Client(api_key=api_key)

    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        )
    ]

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        system_instruction=[types.Part.from_text(text=SYSTEM_INSTRUCTION)],
    )

    response_text = ""
    for attempt in range(max_retries + 1):
        response_text = ""
        try:
            for chunk in client.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config=config,
            ):
                if chunk.text:
                    response_text += chunk.text
            break
        except (genai_errors.ClientError, genai_errors.ServerError) as exc:
            mapped_error = _map_genai_error(exc, model_name=model_name)
            retryable = mapped_error.status_code in {429, 503}
            if retryable and attempt < max_retries:
                computed_retry = int(math.ceil(retry_base_seconds * (2**attempt)))
                retry_after = mapped_error.retry_after_seconds or computed_retry
                retry_after = max(1, min(retry_after, 10))
                LOGGER.warning(
                    "Gemini request failed for model %s (%s). Retrying in %ss (attempt %s/%s).",
                    model_name,
                    mapped_error.error_code,
                    retry_after,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(retry_after)
                continue
            raise mapped_error from exc
        except Exception as exc:
            raise AIServiceError(
                "Unexpected Gemini integration failure.",
                status_code=502,
                error_code="AI_UNEXPECTED_ERROR",
            ) from exc

    if not response_text.strip():
        raise AIServiceError(
            "Gemini returned an empty response.",
            status_code=502,
            error_code="AI_EMPTY_RESPONSE",
        )

    with open(json_path, "w", encoding="utf-8") as json_file:
        json_file.write(response_text)

    return response_text


if __name__ == "__main__":
    print(generate())
