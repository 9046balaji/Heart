"""
Startup script for Cardio AI Assistant Backend Services
Run with: python run_services.py

This script starts:
1. Ollama (with gemma3:1b model check/pull)
2. NLP Service (FastAPI on port 5001)
3. Frontend (React/Vite on port 5173)
"""
import subprocess
import sys
import os
import time
import signal
import requests
import json
import socket
import logging
from datetime import datetime
from pathlib import Path

# Set up logging
LOG_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"services_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

logger.info("=" * 70)
logger.info("Cardio AI Assistant - Service Startup Log")
logger.info(f"Log file: {LOG_FILE}")
logger.info("=" * 70)

def is_port_open(port):
    """Check if a port is open on localhost"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def verify_service_health(service_name, port, max_retries=15):
    """Verify if a service is responding on the given port"""
    logger.info(f"Verifying {service_name} health on port {port}")
    retry_delay = 0.5  # Reduced from 1 second to 0.5 seconds for faster startup
    for attempt in range(max_retries):
        try:
            if is_port_open(port):
                logger.info(f"{service_name} is responding on port {port}")
                return True
            time.sleep(retry_delay)
        except Exception as e:
            logger.debug(f"Health check attempt {attempt + 1} failed for {service_name}: {e}")
            time.sleep(retry_delay)
    
    logger.warning(f"{service_name} on port {port} did not respond after {max_retries} attempts")
    return False

def check_ollama_model(model_name="gemma3:1b"):
    """Check if Ollama model exists, pull if not"""
    print(f"\n[1.5/5] Checking for model {model_name}...")
    logger.info(f"Checking for Ollama model: {model_name}")
    
    try:
        # Check if model exists
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
        if model_name in result.stdout:
            print(f"      [OK] Model {model_name} found.")
            logger.info(f"Ollama model {model_name} found.")
            return True
            
        print(f"      [INFO] Model {model_name} not found. Pulling (this may take a while)...")
        logger.info(f"Model {model_name} not found. Starting pull...")
        subprocess.run(['ollama', 'pull', model_name], check=True)
        print(f"      [OK] Model {model_name} pulled successfully.")
        logger.info(f"Model {model_name} pulled successfully.")
        return True
    except Exception as e:
        print(f"      [ERROR] Failed to check/pull model: {e}")
        logger.error(f"Failed to check/pull model {model_name}: {e}")
        return False

def warm_up_gpu(model_name="gemma3:1b"):
    """Send a tiny request to warm up the GPU"""
    # Check if GPU warmup should be skipped (for faster development startup)
    if os.getenv('SKIP_GPU_WARMUP') == '1':
        print(f"⚡ GPU warmup skipped (SKIP_GPU_WARMUP=1)")
        logger.info("GPU warmup skipped - development mode enabled")
        return
    
    print(f"\n[2/5] Warming up GPU with {model_name}...")
    logger.info(f"Warming up GPU with model {model_name}")
    try:
        payload = {
            "model": model_name,
            "prompt": "hi",
            "stream": False
        }
        requests.post("http://localhost:11434/api/generate", json=payload, timeout=120)
        print("      [OK] GPU Loaded! Model is ready in memory.")
        logger.info("GPU warmup completed successfully.")
    except Exception as e:
        print(f"      [WARNING] Warm-up failed: {e}")
        logger.warning(f"GPU warmup failed: {e}")

def main():
    project_root = os.path.dirname(os.path.abspath(__file__))
    processes = []
    service_logs = {}  # Dictionary to store log file handles for each service
    
    logger.info(f"Project root: {project_root}")
    
    print("=" * 60)
    print("Cardio AI Assistant - Full Stack Startup")
    print("=" * 60)
    logger.info("=" * 70)
    logger.info("Starting Cardio AI Assistant services")
    logger.info("=" * 70)
    
    # --- STEP 1: START OLLAMA ---
    print("\n[1/4] Starting Ollama Service...")
    logger.info("STEP 1: Starting Ollama Service")
    if is_port_open(11434):
        print("      [OK] Ollama is already running on port 11434")
        logger.info("Ollama is already running on port 11434")
    else:
        logger.info("Starting Ollama process")
        ollama_process = subprocess.Popen(
            ['ollama', 'serve'],
            cwd=project_root,
            env={**os.environ, 'OLLAMA_KEEP_ALIVE': '24h'}
        )
        processes.append(('Ollama', ollama_process))
        logger.info(f"Ollama process started with PID {ollama_process.pid}")
        
        # Wait for Ollama to start
        print("      Waiting for Ollama to initialize...")
        logger.info("Waiting for Ollama to initialize...")
        if verify_service_health("Ollama", 11434, max_retries=15):
            print("      [OK] Ollama is online")
            logger.info("Ollama service is online on port 11434")
        else:
            print("      [ERROR] Ollama failed to start.")
            logger.error("Ollama failed to start after 15 retries")
            sys.exit(1)

    # --- STEP 1.5: CHECK MODEL ---
    check_ollama_model()

    # --- STEP 2: WARM UP GPU ---
    warm_up_gpu()
    
    # --- STEP 3: START NLP SERVICE ---
    print("\n[3/4] Starting NLP Service...")
    logger.info("STEP 3: Starting NLP Service")
    nlp_service_path = os.path.join(project_root, 'nlp-service')
    print(f"      Starting NLP Service from: {nlp_service_path}")
    logger.info(f"Starting NLP Service from: {nlp_service_path}")
    
    # Set up environment with PYTHONPATH for proper imports
    env = {**os.environ, 'NLP_SERVICE_PORT': '5001'}
    env['PYTHONPATH'] = nlp_service_path + os.pathsep + env.get('PYTHONPATH', '')
    
    # Create log file for NLP service
    nlp_log_path = LOG_DIR / "nlp_service.log"
    nlp_log_file = open(nlp_log_path, 'w')
    service_logs['NLP Service'] = nlp_log_file
    
    nlp_process = subprocess.Popen(
        [sys.executable, 'main.py'],
        cwd=nlp_service_path,
        env=env,
        stdout=nlp_log_file,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    processes.append(('NLP Service', nlp_process))
    logger.info(f"NLP Service started with PID {nlp_process.pid}, logs: {nlp_log_path}")
    
    # Wait for NLP service to start
    print("      Waiting for NLP Service to initialize...")
    logger.info("Waiting for NLP Service to initialize on port 5001...")
    if verify_service_health("NLP Service", 5001, max_retries=30):
        print("      [OK] NLP Service is online")
        logger.info("NLP Service is online on port 5001")
    else:
        print("      [ERROR] NLP Service failed to start.")
        logger.error("NLP Service failed to start after 30 retries. Check logs: " + str(nlp_log_path))
        sys.exit(1)
    
    # --- STEP 4: START FRONTEND ---
    print("\n[4/4] Starting Frontend Interface...")
    logger.info("STEP 4: Starting Frontend")
    frontend_path = os.path.join(project_root, 'cardio-ai-assistant')
    logger.info(f"Starting Frontend from: {frontend_path}")
    
    # Use npm.cmd on Windows, npm on others
    npm_cmd = 'npm.cmd' if os.name == 'nt' else 'npm'
    
    # Create log file for frontend
    frontend_log_path = LOG_DIR / "frontend.log"
    frontend_log_file = open(frontend_log_path, 'w')
    service_logs['Frontend'] = frontend_log_file
    
    frontend_process = subprocess.Popen(
        [npm_cmd, 'run', 'dev'],
        cwd=frontend_path,
        stdout=frontend_log_file,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    processes.append(('Frontend', frontend_process))
    logger.info(f"Frontend started with PID {frontend_process.pid}, logs: {frontend_log_path}")
    
    # Wait for Frontend to start
    print("      Waiting for Frontend to initialize...")
    logger.info("Waiting for Frontend to initialize on port 5174...")
    if verify_service_health("Frontend", 5174, max_retries=30):
        print("      [OK] Frontend is online")
        logger.info("Frontend is online on port 5174")
    else:
        print("      [WARNING] Frontend taking time to start. Continuing anyway...")
        logger.warning("Frontend taking longer than expected to start")
    
    # --- FINAL SUMMARY ---
    print("\n" + "=" * 60)
    print("All services are starting up!")
    print("=" * 60)
    print("\nService URLs:")
    print("  - Frontend:    http://localhost:5174")
    print("  - NLP Service: http://localhost:5001")
    print("  - Ollama:      http://localhost:11434")
    print(f"\nLog files location: {LOG_DIR}")
    print("\nPress Ctrl+C to stop all services.")
    print("=" * 60)
    
    logger.info("=" * 70)
    logger.info("All services started successfully!")
    logger.info(f"Log directory: {LOG_DIR}")
    logger.info("=" * 70)
    
    def signal_handler(sig, frame):
        print("\n\nShutting down services...")
        logger.info("Shutting down all services...")
        for name, proc in processes:
            print(f"  Stopping {name}...")
            logger.info(f"Stopping {name} (PID: {proc.pid})")
            # On Windows, terminate() might not kill the whole process tree (like npm -> node)
            # But for dev purposes, this is usually sufficient or requires taskkill
            proc.terminate()
        
        # Close all log files
        print("\nClosing log files...")
        logger.info("Closing log files...")
        for name, log_file in service_logs.items():
            try:
                log_file.close()
                logger.info(f"Closed log file for {name}")
            except Exception as e:
                logger.warning(f"Error closing log file for {name}: {e}")
        
        print("All services stopped.")
        logger.info("All services stopped. Logs saved to: " + str(LOG_DIR))
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Wait for processes
    try:
        while True:
            for name, proc in processes:
                if proc.poll() is not None:
                    print(f"\n{name} exited with code {proc.returncode}")
                    logger.warning(f"{name} exited with code {proc.returncode}")
                    # If a critical service dies, maybe we should exit?
                    # For now, just log it.
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == '__main__':
    main()
