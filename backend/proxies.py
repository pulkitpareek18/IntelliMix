import requests
import random
import threading
import time
import os
from datetime import datetime

# URL for fetching fresh proxies
PROXY_URL = "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt"

# Track the last update time
last_update_time = None

# Lock for thread safety
proxy_lock = threading.Lock()

# Initialize with some default proxies in case fetching fails on first run
proxies = {
    'http': 'http://148.66.6.211:80',
    'https': 'http://148.66.6.211:80'
}

# List to store all available proxies
all_proxies = []

def fetch_proxies():
    """Fetch fresh proxies from the source URL"""
    global all_proxies, last_update_time
    
    try:
        response = requests.get(PROXY_URL, timeout=10)
        if response.status_code == 200:
            # Parse the proxy list - format is IP:PORT on each line
            proxy_list = response.text.strip().split('\n')
            
            # Convert to the proper format and store
            formatted_proxies = []
            for proxy in proxy_list:
                if proxy and ':' in proxy:  # Ensure it's a valid entry
                    proxy = proxy.strip()
                    formatted_proxy = {
                        'http': f'{proxy}',
                    }
                    formatted_proxies.append(formatted_proxy)
            
            # Update the proxy list with a lock to ensure thread safety
            with proxy_lock:
                all_proxies = formatted_proxies
                last_update_time = datetime.now()
                
            print(f"[{datetime.now()}] Successfully fetched {len(all_proxies)} proxies")
            return True
        else:
            print(f"[{datetime.now()}] Failed to fetch proxies: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"[{datetime.now()}] Error fetching proxies: {str(e)}")
        return False

def get_proxy():
    """Get a random proxy from the available ones"""
    with proxy_lock:
        if all_proxies:
            return random.choice(all_proxies)
        return proxies  # Return the default if no proxies available

def test_proxy(proxy_config):
    """Test if a proxy is working"""
    try:
        response = requests.get("https://httpbin.org/ip", 
                               proxies=proxy_config, 
                               timeout=5)
        return response.status_code == 200
    except:
        return False

def get_working_proxy(max_attempts=5):
    """Try to get a working proxy with multiple attempts"""
    for _ in range(max_attempts):
        proxy = get_proxy()
        if test_proxy(proxy):
            return proxy
    
    # If no working proxy found, return the default
    print("[WARNING] No working proxy found after multiple attempts")
    return proxies

def update_proxies_periodically():
    """Update proxies every 30 minutes"""
    while True:
        success = fetch_proxies()
        
        # Write the current status to a file for monitoring
        try:
            status_info = {
                "last_update": last_update_time.strftime("%Y-%m-%d %H:%M:%S") if last_update_time else "Never",
                "proxy_count": len(all_proxies),
                "update_success": success
            }
            
            with open(os.path.join(os.path.dirname(__file__), "proxy_status.txt"), "w") as f:
                for key, value in status_info.items():
                    f.write(f"{key}: {value}\n")
        except Exception as e:
            print(f"Error writing status file: {e}")
        
        # Sleep for 30 minutes (1800 seconds)
        time.sleep(1800)

# Start the background updater thread
updater_thread = threading.Thread(target=update_proxies_periodically, daemon=True)
# updater_thread.start() # Commented this because we are starting the updater thread from app.py

# # Initial fetch of proxies
# fetch_proxies()

# For testing purposes
if __name__ == "__main__":
    print("Fetching proxies...")
    fetch_proxies()
    print(f"Found {len(all_proxies)} proxies")
    
    if all_proxies:
        print("\nTesting a random proxy:")
        random_proxy = get_proxy()
        print(f"Selected proxy: {random_proxy}")
        works = test_proxy(random_proxy)
        print(f"Proxy working: {works}")
        
        if works:
            print("\nGetting working proxy:")
            working_proxy = get_working_proxy()
            print(f"Working proxy found: {working_proxy}")
    
    print(get_working_proxy())  # Call to ensure we have a working proxy for the main thread