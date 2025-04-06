import pytubefix
from pytubefix import Search

def get_youtube_url(title, artist):
    """
    Search for a song on YouTube based on title and artist name, then return its URL.
    
    Args:
        title (str): The title of the song
        artist (str): The name of the artist
        
    Returns:
        str: URL of the first search result, or None if no results found
    """
    try:
        # Create a search query combining title and artist
        query = f"{title} {artist} official"
        
        # Create a Search object with use_po_token=True
        search_results = Search(query, use_po_token=True).results
        
        # Check if we have any results
        if not search_results:
            return None
            
        # Get the first result's URL
        first_result = search_results[0]
        video_url = f"https://www.youtube.com/watch?v={first_result.video_id}"
        
        return video_url
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None

# Example usage
if __name__ == "__main__":
    # Test the function
    test_title = "angrezi beat"
    test_artist = "honey singh"
    
    result = get_youtube_url(test_title, test_artist)
    print(f"URL: {result}")