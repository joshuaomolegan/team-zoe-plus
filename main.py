import os
import requests
import os

from tqdm import tqdm
from html_modifier import parse_html
from flask import Flask, request

from accessibility_editor import AccessibilityEditor
from contrast_editor import ContrastEditor
from utils import debug_picklify
import base64
from dotenv import load_dotenv

load_dotenv()

try:
   WAVE_API_KEY = os.environ["WAVE_API_KEY"]
except KeyError:
   raise KeyError("Please set the WAVE_API_KEY environment variable to your Wave API key.")

app = Flask(__name__)
app.debug = True

ACCESSIBILITY_API_URL = "https://alphagov.github.io/accessibility-tool-audit/test-cases.html" 
HTTP_EMPTY_RESPONSE = 200
WAVE_API_KEY = os.getenv("WAVE_API_KEY")

@app.route("/", methods=['GET', 'POST'])
def get_html():
    if request.method == 'POST':
        content = request.json
        url = content["url"]
        html_string = content["html_string"]
        image_arr = content["images"]
        image_bytes_arr = [base64.b64decode(image.encode('utf-8')) for image in image_arr]

        dom = parse_html(html_string)
        accessibility_editor = AccessibilityEditor(dom)
        contrast_editor = ContrastEditor(dom)
        
        return process_analysis(
           query_accessibility_errors(ACCESSIBILITY_API_URL), 
           accessibility_editor, 
           contrast_editor
         )
    
    return "", HTTP_EMPTY_RESPONSE

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

@debug_picklify
def query_accessibility_errors(website: str):
  response = requests.get(
     "https://wave.webaim.org/api/request",
     params = {
        "key": WAVE_API_KEY,
        "url": website,
        "format": "json",
        "reporttype": "3"
     }
  )

  if response.status_code != 200:
     raise RuntimeError(f"Wave failed with code {response}. Full response: {response}")

  return response.json()

def process_analysis(
      results: dict, 
      accessibility_editor: AccessibilityEditor,
      contrast_editor: ContrastEditor
   ):
   print(f"Visual analysis URL: {results['statistics']['waveurl']}")
   print(f"Total element count: {results['statistics']['totalelements']}")

   errors = results['categories']['error']['items']
   alerts = results['categories']['alert']['items']
   contrast_errors = results['categories']['contrast']['items']

   with tqdm(total = len(errors) + len(contrast_errors)) as pbar:
      for error_type, error in errors.items():
         pbar.set_description(f"Patching {error_type}...")
         
         try:
            accessibility_editor.handle_accessibility_error(error_type, error)
         except RuntimeError:
            # TODO: Remove this!
            pass
         
         pbar.update()

      for contrast_type, contrast_error in contrast_errors.items():
         pbar.set_description(f"Fixing contrast {contrast_type}...")
         
         try:
            contrast_editor.handle_contrast_error(contrast_type, contrast_error)
         except RuntimeError:
            # TODO: Remove this!
            pass
         
         pbar.update()      
   
   # TODO: Handle alerts!

if __name__ == "__main__":
   app.run()
