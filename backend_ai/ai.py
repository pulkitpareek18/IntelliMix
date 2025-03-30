import base64
import os
from google import genai
from google.genai import types
import pytubefix
import json
from io import StringIO
import re
from search import get_youtube_url

def generate():
    client = genai.Client(
        api_key="AIzaSyC7j_xulPS1SP8yaMbCw71oSRUXQqQnxKg",
    )

    model = "gemini-2.0-flash"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text="""create a parody of honey singh songs"""),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        system_instruction=[
            types.Part.from_text(text="""The user will ask you to make a mix of some songs from YouTube. Based on the prompt, you have to do the following:

Analyze the user's request and identify the songs and their relevant parts that would fit well together.

Search for the official or high-quality versions of the songs on YouTube.

Choose timestamps from each song that blend well in the mix and maintain a consistent vibe or theme.

Consider transitions and the overall flow to create a smooth-sounding parody or mashup.

Output the result in the following JSON format only no starting and trainling backticks and json type encoding, just pure json:

{
  \"mixTitle\": \"Descriptive title of the mix\",
  \"songs\": [
    {
      \"title\": \"Song Title\",
      \"artist\": \"Artist Name\",
      \"url\": \"YouTube URL\",
      \"startTime\": \"HH:MM:SS\",
      \"endTime\": \"HH:MM:SS\",
    },
    {
      \"title\": \"Song Title\",
      \"artist\": \"Artist Name\",
      \"url\": \"YouTube URL\",
      \"startTime\": \"HH:MM:SS\",
      \"endTime\": \"HH:MM:SS\",
    }
  ]
}
"""),
        ],
    )

    full_response = ""
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        print(chunk.text, end="")
        full_response += chunk.text

    with open ("audio_data.json", "w") as f:
        f.write(full_response)

    url_start_end = []

    


    # Parse the output JSON from the API response

    # Capture the API output
    output = chunk.text
    # Save the response to a JSON file

    print(output)
   

if __name__ == "__main__":
    generate()