#!/usr/bin/env python3
"""
Lightweight healthcheck for Docker.
Exits 0 if healthy, 1 if unhealthy.
"""
import sys
import urllib.request
import os

def check_health():
    port = os.getenv("NLP_SERVICE_PORT", "5001")
    url = f"http://localhost:{port}/" # Root endpoint returns status
    
    try:
        response = urllib.request.urlopen(
            url,
            timeout=2
        )
        
        if response.status == 200:
            return 0  # Healthy
        else:
            print(f"Health endpoint returned {response.status}", file=sys.stderr)
            return 1  # Unhealthy
    
    except Exception as e:
        print(f"Healthcheck failed: {e}", file=sys.stderr)
        return 1  # Unhealthy

if __name__ == "__main__":
    sys.exit(check_health())
