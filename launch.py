import subprocess
import threading
import time

def run_django():
    """Start Django development server"""
    subprocess.run(["python3", "manage.py", "runserver", "0.0.0.0:8000"])

def run_streamlit():
    """Start Streamlit app"""
    subprocess.run(["streamlit", "run", "app.py", "--server.port=8501"])

if __name__ == "__main__":
    # Start Django in a thread
    django_thread = threading.Thread(target=run_django)
    django_thread.daemon = True  # Thread will exit when main program exits
    django_thread.start()

    # Start Streamlit in main thread
    run_streamlit()

    # Keep the script running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down servers...")
