import json
import re

def parse_mix_json(json_str):
    """
    Parse the JSON string and extract url, start time, and end time for each song.
    Returns a list of [url, start_time_seconds, end_time_seconds]
    """
    try:
        # Handle potential JSON errors
        data = json.loads(json_str)
        
        url_start_end = []
        
        for song in data.get("songs", []):
            url = song.get("url", "")
            
            # Convert start time and end time from "HH:MM:SS" format to seconds
            start_time = convert_time_to_seconds(song.get("startTime", "00:00:00"))
            end_time = convert_time_to_seconds(song.get("endTime", "00:00:00"))
            
            url_start_end.append([url, start_time, end_time])
            
        return url_start_end
    
    except json.JSONDecodeError as e:
        # Handle malformed JSON
        print(f"Error parsing JSON: {e}")
        # Try to extract the valid part from the string
        fixed_json = fix_json(json_str)
        if fixed_json:
            try:
                return parse_mix_json(fixed_json)
            except Exception as e2:
                print(f"Failed to fix JSON: {e2}")
                return []
        else:
            return []

def convert_time_to_seconds(time_str):
    """
    Convert time string in format "HH:MM:SS" or "MM:SS" to seconds
    """
    parts = time_str.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = map(int, parts)
        return hours * 3600 + minutes * 60 + seconds
    elif len(parts) == 2:
        minutes, seconds = map(int, parts)
        return minutes * 60 + seconds
    else:
        try:
            return int(time_str)
        except ValueError:
            return 0

def fix_json(json_str):
    """
    Attempt to fix malformed JSON by finding valid JSON object
    """
    # Look for a JSON object between { and }
    match = re.search(r'({[\s\S]*})', json_str, re.DOTALL)
    if match:
        potential_json = match.group(1)
        # Try to clean up any embedded error messages
        clean_json = re.sub(r'Error parsing JSON:.*', '', potential_json)
        return clean_json
    return None

def get_json_input():
    """
    Get multi-line JSON input from user or file
    """
    print("Enter or paste your JSON (press Ctrl+D on Unix/Linux or Ctrl+Z followed by Enter on Windows to finish):")
    lines = []
    
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    
    return '\n'.join(lines)

if __name__ == "__main__":
    # Try to load JSON from file
    try:
        with open('audio_data.json', 'r') as file:
            json_input = file.read()
    except FileNotFoundError:
        print("audio_data.json not found. Requesting manual input.")
        json_input = get_json_input()
    
    # Parse JSON and get url_start_end list
    result = parse_mix_json(json_input)

    url_start_end = []
    
    if result:
        print("\nExtracted URL, start time, and end time:")
        print(f"url_start_end = {result}")
        
        # Display in a more readable format
        print("\nReadable format:")
        for i, item in enumerate(result, 1):
            url_start_end.append([item[0],item[1],item[2]])
    else:
        print("Failed to parse JSON. Please check the input format.")

        print(url_start_end)

