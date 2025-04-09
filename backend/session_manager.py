import os
import uuid
import shutil
import time
import threading
from datetime import datetime, timedelta
import re

class SessionManager:
    def __init__(self, base_dir="user_sessions", expiry_seconds=300):
        self.base_dir = base_dir
        self.expiry_seconds = expiry_seconds
        self.sessions = {}  # Dictionary to track active sessions
        self.lock = threading.Lock()
        
        # Create base directory if it doesn't exist
        os.makedirs(base_dir, exist_ok=True)
        
        # Load existing sessions from disk
        self._load_existing_sessions()
        
        # Start the cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_expired_sessions, daemon=True)
        self.cleanup_thread.start()
    
    def _load_existing_sessions(self):
        """Load existing session directories if server was restarted"""
        print("Loading existing sessions from disk...")
        try:
            if os.path.exists(self.base_dir):
                session_dirs = [d for d in os.listdir(self.base_dir) 
                              if os.path.isdir(os.path.join(self.base_dir, d)) 
                              and self._is_valid_uuid(d)]
                
                loaded_count = 0
                for session_id in session_dirs:
                    session_dir = os.path.join(self.base_dir, session_id)
                    
                    # Try to determine last access time from directory metadata
                    try:
                        # Get the most recent file modification time in the session directory
                        last_modified = self._get_latest_modified_time(session_dir)
                        
                        # Add session to in-memory dictionary
                        self.sessions[session_id] = {
                            "created": datetime.fromtimestamp(os.path.getctime(session_dir)),
                            "last_accessed": datetime.fromtimestamp(last_modified),
                            "dir": session_dir
                        }
                        loaded_count += 1
                    except Exception as e:
                        print(f"Error loading session {session_id}: {e}")
                
                print(f"Loaded {loaded_count} existing sessions")
        except Exception as e:
            print(f"Error scanning session directory: {e}")
    
    def _is_valid_uuid(self, uuid_string):
        """Check if string is a valid UUID"""
        pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', 
            re.IGNORECASE
        )
        return bool(pattern.match(uuid_string))
    
    def _get_latest_modified_time(self, directory):
        """Get the most recent file modification time in a directory tree"""
        latest_time = os.path.getmtime(directory)
        
        for root, dirs, files in os.walk(directory):
            for name in files:
                file_path = os.path.join(root, name)
                mod_time = os.path.getmtime(file_path)
                if mod_time > latest_time:
                    latest_time = mod_time
                    
            for name in dirs:
                dir_path = os.path.join(root, name)
                mod_time = os.path.getmtime(dir_path)
                if mod_time > latest_time:
                    latest_time = mod_time
                    
        return latest_time
    
    def create_session(self):
        """Create a new session with unique directories"""
        with self.lock:
            session_id = str(uuid.uuid4())
            session_dir = os.path.join(self.base_dir, session_id)
            
            # Create session directory structure
            os.makedirs(session_dir, exist_ok=True)
            os.makedirs(os.path.join(session_dir, "temp"), exist_ok=True)
            os.makedirs(os.path.join(session_dir, "temp", "split"), exist_ok=True)
            os.makedirs(os.path.join(session_dir, "temp", "output"), exist_ok=True)
            os.makedirs(os.path.join(session_dir, "static", "video_dl"), exist_ok=True)
            os.makedirs(os.path.join(session_dir, "static", "audio_dl"), exist_ok=True)
            os.makedirs(os.path.join(session_dir, "static", "output"), exist_ok=True)
            os.makedirs(os.path.join(session_dir, "csv"), exist_ok=True)
            
            # Record session with timestamp
            self.sessions[session_id] = {
                "created": datetime.now(),
                "last_accessed": datetime.now(),
                "dir": session_dir
            }
            
            print(f"Created new session: {session_id}")
            return session_id
    
    def get_session_dir(self, session_id):
        """Get the directory for a session and update last access time"""
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id]["last_accessed"] = datetime.now()
                # Also update the directory modification time to reflect access
                try:
                    os.utime(self.sessions[session_id]["dir"], None)
                except Exception:
                    pass  # Ignore errors updating directory time
                return self.sessions[session_id]["dir"]
                
            # Session not found in dictionary, try to locate on disk
            potential_dir = os.path.join(self.base_dir, session_id)
            if os.path.exists(potential_dir) and self._is_valid_uuid(session_id):
                # Rehydrate the session object
                self.sessions[session_id] = {
                    "created": datetime.fromtimestamp(os.path.getctime(potential_dir)),
                    "last_accessed": datetime.now(),
                    "dir": potential_dir
                }
                print(f"Rehydrated lost session: {session_id}")
                return potential_dir
                
            return None
    
    def clear_session_temp(self, session_id):
        """Clear temporary files for a specific session"""
        with self.lock:
            if session_id in self.sessions:
                temp_dir = os.path.join(self.sessions[session_id]["dir"], "temp")
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        try:
                            os.remove(os.path.join(root, file))
                        except Exception as e:
                            print(f"Error removing file in session {session_id}: {e}")
                            
                # Update last access time
                self.sessions[session_id]["last_accessed"] = datetime.now()
    
    def clear_session_output(self, session_id):
        """Clear output files for a specific session"""
        with self.lock:
            if session_id in self.sessions:
                session_dir = self.sessions[session_id]["dir"]
                output_paths = [
                    os.path.join(session_dir, "static", "video_dl"),
                    os.path.join(session_dir, "static", "audio_dl"),
                    os.path.join(session_dir, "static", "output"),
                    os.path.join(session_dir, "temp", "output")
                ]
                
                for path in output_paths:
                    if os.path.exists(path):
                        for root, dirs, files in os.walk(path):
                            for file in files:
                                try:
                                    os.remove(os.path.join(root, file))
                                except Exception as e:
                                    print(f"Error removing output file in session {session_id}: {e}")
                
                # Update last access time
                self.sessions[session_id]["last_accessed"] = datetime.now()
    
    def delete_session(self, session_id):
        """Delete a session and its directories"""
        with self.lock:
            if session_id in self.sessions:
                try:
                    session_dir = self.sessions[session_id]["dir"]
                    if os.path.exists(session_dir):
                        shutil.rmtree(session_dir)
                    del self.sessions[session_id]
                    print(f"Deleted session {session_id}")
                    return True
                except Exception as e:
                    print(f"Error deleting session {session_id}: {e}")
            elif os.path.exists(os.path.join(self.base_dir, session_id)):
                # Session exists on disk but not in memory
                try:
                    shutil.rmtree(os.path.join(self.base_dir, session_id))
                    print(f"Deleted orphaned session directory {session_id}")
                    return True
                except Exception as e:
                    print(f"Error deleting orphaned session {session_id}: {e}")
            return False
    
    def _cleanup_expired_sessions(self):
        """Background thread to clean up expired sessions"""
        print("Cleanup thread started!")
        cleanup_count = 0
        
        while True:
            time.sleep(5)  # Check every 5 seconds for easier testing
            cleanup_count += 1
            now = datetime.now()
            expired_sessions = []
            
            # First check in-memory sessions
            with self.lock:
                for session_id, session_data in list(self.sessions.items()):
                    if now - session_data["last_accessed"] > timedelta(seconds=self.expiry_seconds):
                        expired_sessions.append(session_id)
            
            # Delete expired in-memory sessions
            for session_id in expired_sessions:
                print(f"Cleaning up expired session: {session_id} (cleanup cycle #{cleanup_count})")
                self.delete_session(session_id)
            
            # Now scan directory for orphaned sessions not in our dictionary
            if cleanup_count % 12 == 0:  # Check disk every minute (12 * 5 seconds)
                print("Scanning disk for orphaned sessions...")
                try:
                    for item in os.listdir(self.base_dir):
                        item_path = os.path.join(self.base_dir, item)
                        if os.path.isdir(item_path) and self._is_valid_uuid(item) and item not in self.sessions:
                            # Check if directory is old based on modification time
                            last_modified = self._get_latest_modified_time(item_path)
                            age_seconds = (now - datetime.fromtimestamp(last_modified)).total_seconds()
                            
                            if age_seconds > self.expiry_seconds:
                                print(f"Removing orphaned session directory: {item} (age: {age_seconds:.1f}s)")
                                try:
                                    shutil.rmtree(item_path)
                                except Exception as e:
                                    print(f"Error removing orphaned session: {e}")
                except Exception as e:
                    print(f"Error scanning for orphaned sessions: {e}")
                
            # Log activity periodically even if no sessions were removed
            if not expired_sessions and cleanup_count % 12 == 0:
                active_count = len(self.sessions)
                print(f"Cleanup thread active, cycle #{cleanup_count}, {active_count} active sessions")

