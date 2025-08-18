# api_example.py
# FastAPIによるAPIエンドポイント雛形
from fastapi import FastAPI, UploadFile, File
from processor import handle_new_file

app = FastAPI()

@app.post('/upload')
def upload_file(file: UploadFile = File(...)):
    # 一時保存してhandle_new_fileに渡す例
    temp_path = f'/tmp/{file.filename}'
    with open(temp_path, 'wb') as f:
        f.write(file.file.read())
    handle_new_file(temp_path)
    return {'status': 'ok'}
