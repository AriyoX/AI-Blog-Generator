import os
from mistralai import Mistral
from dotenv import load_dotenv
load_dotenv()

# Set your API key
api_key = os.environ.get("MISTRAL_API_KEY")

# Initialize the Mistral client
client = Mistral(api_key=api_key)

# Define the model and prompt
model = "mistral-small-latest"
transcript = ("I know how to make tea, it takes a variety of steps, ranging from putting the bag of tea into water to stirring and adding sugar")
prompt = (f"Based on the following transcript from a YouTube video, write a comprehensive blog article. "
          f"Write it based on the transcript, but do not make it look like a YouTube video, make it look like a proper blog article:\n\n{transcript}\n\nArticle:")

# Generate content using the chat endpoint
chat_response = client.chat.complete(
    model=model,
    messages=[
        {
            "role": "user",
            "content": prompt,
        },
    ]
)

# Print the response
print(chat_response.choices[0].message.content)
