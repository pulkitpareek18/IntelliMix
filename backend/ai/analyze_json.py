import json
import re

def parse_mix_json(json_str):
    """
    Parse the JSON string and extract title, artist, start time, and end time for each song.
    Returns a list of [title, artist, start_time_seconds, end_time_seconds]
    """
    try:
        # Handle potential JSON errors
        data = json.loads(json_str)
        
        url_start_end = []
        
        for song in data.get("songs", []):
            title = song.get("title", "")
            artist = song.get("artist", "")
            
            # Convert start time and end time from "HH:MM:SS" format to seconds
            start_time = convert_time_to_seconds(song.get("startTime", "00:00:00"))
            end_time = convert_time_to_seconds(song.get("endTime", "00:00:00"))
            
            url_start_end.append([title, artist, start_time, end_time])
            
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

def load_json_from_file(file_path='audio_data.json'):
    """
    Load JSON data from a file
    
    Args:
        file_path (str): Path to the JSON file
        
    Returns:
        str: JSON string content or None if file not found
    """
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        print(f"{file_path} not found.")
        return None

def analyze_mix(json_str=None, file_path='audio_data.json'):
    """
    Main function to analyze audio mix data
    
    Args:
        json_str (str, optional): JSON string to parse directly
        file_path (str, optional): Path to JSON file to load
        
    Returns:
        list: List of [title, artist, start_time, end_time] for each song
    """
    # If no JSON string provided, try to load from file
    if json_str is None:
        json_str = load_json_from_file(file_path)
        
    
    # Parse JSON and get song information
    result = parse_mix_json(json_str)
    
    return result

if __name__ == "__main__":
    # When run directly, execute analyze_mix and display results
    result = analyze_mix()
    
    if result:
        print("\nExtracted song information:")
        print(result)
        
        # Display in a more readable format
        print("\nReadable format:")
        for i, item in enumerate(result, 1):
            print(f"Song {i}: {item[0]} by {item[1]}, Start: {item[2]}s, End: {item[3]}s")
    else:
        print("No valid song information found.")