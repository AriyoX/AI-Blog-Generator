import pathlib
import textwrap

import google.generativeai as genai

from IPython.display import display
from IPython.display import Markdown


def to_markdown(text):
  text = text.replace('•', '  *')
  return Markdown(textwrap.indent(text, '> ', predicate=lambda _: True))

GOOGLE_API_KEY= "AIzaSyCBek4ojoK-IcYVPlAPxEXNRNtdEO4zVVU"

genai.configure(api_key=GOOGLE_API_KEY)

for m in genai.list_models():
  if 'generateContent' in m.supported_generation_methods:
    print(m.name)

model = genai.GenerativeModel('gemini-pro')

transcript = "I know how to make tea, it takes a variety of steps, ranging from putting the bag of tea into water to strring and adding sugar"
prompt = f"Based on the following transcript from a youtube video, write a comprehensive blog article. write it based on the transcript, but do not make it look like a youtube video, make it look like a proper blog article:\n\n{transcript}\n\nArticle:"

response = model.generate_content(prompt)

x= to_markdown(response.text)
print(x)