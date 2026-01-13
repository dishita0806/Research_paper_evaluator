from fastapi import FastAPI, UploadFile, File
import pdfplumber
import io
from fastapi.responses import RedirectResponse

app = FastAPI()

@app.get("/", include_in_schema=False)
async def rediret_to_docs():
    return RedirectResponse(url="/docs")

@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    # Read PDF file as bytes
    pdf_bytes = await file.read()

    extracted_text = ""

    # Open PDF from bytes
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            extracted_text += page.extract_text() or ""

    return {
        "filename": file.filename,
        "text_preview": extracted_text[:1000]  # first 1000 chars only
    }
