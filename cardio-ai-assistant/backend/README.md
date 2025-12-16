# Health Super-App Backend

This directory contains the backend code for the Health Super-App, built with FastAPI.

## Setup and Installation

1.  **Navigate to the backend directory:**

    ```bash
    cd backend
    ```

2.  **Create a virtual environment:**

    ```bash
    python -m venv venv
    source venv/bin/activate
    ```

3.  **Install the required dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

## Running the Server

Once the dependencies are installed, you can run the FastAPI server using `uvicorn`:

```bash
uvicorn main:app --reload
```

This will start the server on `http://127.0.0.1:8000`. The `--reload` flag enables auto-reloading, so the server will automatically restart whenever you make changes to the code.

## API Documentation

FastAPI automatically generates interactive API documentation. Once the server is running, you can access it at:

*   **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
*   **ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
