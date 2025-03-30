import base64
import os
from google import genai
from google.genai import types
import pytubefix
import json
from io import StringIO
import re
from search import get_youtube_url

def generate(prompt = "create a parody of honey singh songs"):
    client = genai.Client(
        api_key="AIzaSyC7j_xulPS1SP8yaMbCw71oSRUXQqQnxKg",
    )

    model = "gemini-2.0-flash"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=prompt),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        system_instruction=[
            types.Part.from_text(text="""
            
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

What I've noticed that the duration for all the songs you keep them equal to 30 seconds, but it should be different for all the songs, keep it different on the basis of the song and the best part of the song to groove on.

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
    return output
   

if __name__ == "__main__":
    generate()