import asyncio
import sys
import os
import uvicorn

# Inject libs/python into sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'libs', 'python')))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8001)
