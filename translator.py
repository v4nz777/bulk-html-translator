from bs4 import BeautifulSoup, NavigableString
import os
import google.auth
from google.cloud import translate_v2 as translate
import chardet
from tqdm import tqdm
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
import time
import concurrent.futures

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'translate.json'
ERRONEOUS = []

def check_language(text:str):
    is_hindi:bool = False
    is_blank:bool = False
    invalid:bool = False

    try:
        is_hindi = detect(text) == 'hi'
    except LangDetectException:
        invalid = True
    is_blank = not text.strip()
    return is_hindi, invalid, is_blank



def translate_text(text:str, target:str):
    # Set up the Google Cloud credentials
    credentials, project = google.auth.default()
    translate_client = translate.Client(credentials=credentials)
    
    MAX_RETRY = 100
    WAIT_SECONDS = 5
    
    for retry in range(MAX_RETRY):
        try:
            result = translate_client.translate(text, target_language=target)
            return result['translatedText']
        except:
            print(f"Connection error on attempt {retry+1}. Retrying in {WAIT_SECONDS} seconds...")
            time.sleep(WAIT_SECONDS)
            print("Reconnecting...")


def translate_html(file_path:str, target:str='hi'):
    with open(file_path, 'rb') as file:
        content = file.read()
        result = chardet.detect(content)
        encoding = result['encoding']

    if encoding != 'utf-8':
        with open(file_path, 'rb') as file:
            content = file.read()
        content = content.decode(encoding)
        content = content.encode('utf-8')
        with open(file_path, 'wb') as file:
            file.write(content)
        encoding = 'utf-8'

    with open(file_path, 'r', encoding='utf-8') as file:
        try:
            content = file.read()
        except UnicodeDecodeError as d:
            err = {
                "title":f'READ_ERROR: {file}',
                "file": file,
                "path": file_path,
                "encoding": encoding,
                "error": d
            }
            ERRONEOUS.append(err)
            print(err)
            return
        
    soup = BeautifulSoup(content, 'html.parser')
    tags = ["p","h1","h2","h3","h4","h5","h6","span","a","li","strong","em","div","caption","label","button","td","th","title","header","footer","nav","main"]
    

    for tag in tags:
        for tag_element in tqdm(soup.find_all(tag), desc=f"<{file_path}> {tag}", unit="item"):

            for element in tag_element.children:
                if isinstance(element, NavigableString): # Ensures only affecting the text child
                    text = element.strip()
                    is_hindi,invalid,is_blank = check_language(text)
                    if is_blank or is_hindi or invalid:
                        continue

                    translated_text = translate_text(text, target) # Translates valid text
                    element.replace_with(translated_text)

        

        

    with open(file_path, 'w', encoding='utf-8') as file:
        try:
            file.write(str(soup))
        except UnicodeEncodeError as e:
            err = {
                "title":f'WRITE_ERROR: {file}',
                "file": file,
                "path": file_path,
                "encoding": encoding,
                "error": e
            }
            ERRONEOUS.append(err)
            print(err)
            
        

def translate_html_files(directory:str, target:str='hi'):
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if filename.endswith('.html'):
                file_path = os.path.join(root, filename)
                print(f'Translating file {file_path}')
                translate_html(file_path, target)

    print(ERRONEOUS)
    with open("finish_log.txt", "w") as export:
        export.write("\n".join(ERRONEOUS))

def translate_html_files_concurrently(directory:str, target:str='hi'):
    file_paths = []
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if filename.endswith('.html'):
                file_path = os.path.join(root, filename)
                file_paths.append(file_path)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(translate_html, file_path, target) for file_path in file_paths]
        for future in tqdm(concurrent.futures.as_completed(futures), desc="Scanning", unit="future"):
            future.result()

    print(ERRONEOUS)
    with open("finish_log.txt", 'w') as file:
        file.write("\n".join(ERRONEOUS))

if __name__ == '__main__':
    directory = input("Enter the path for scanning: ")
    translate_html_files_concurrently(directory)
