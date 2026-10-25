# -*- coding: utf-8 -*-
"""
Created on Sun Oct 25 21:46:54 2026

@author: rajpr
"""


import json
import urllib.request
import urllib.error

URL = "http://localhost:11434/api/chat"

payload = {
    "model": "qwen2.5:3b",
    "messages": [
        {
            "role": "user",
            "content": (
                "Explain prompt engineering to a beginner in "
                "three bullet points. Keep the answer concise."
            ),
        }
    ],
    "stream": False,
}

request = urllib.request.Request(
    URL,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(request, timeout=300) as response:
        result = json.loads(response.read().decode("utf-8"))

    print("Ollama Python connection successful!")
    print("\nModel response:\n")
    print(result["message"]["content"])

except urllib.error.URLError as error:
    print("Could not connect to Ollama.")
    print("Make sure the Ollama application is running.")
    print("Details:", error)
