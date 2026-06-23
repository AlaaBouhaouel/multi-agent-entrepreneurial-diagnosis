from anthropic import Anthropic
import os
client = Anthropic(os.getenv(API_Key))

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=100,
    messages=[
        {"role": "user", "content": "hello"}
    ]
)

print(response.content)