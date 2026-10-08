FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/models
COPY requirements.txt .
# CPU build of torch first (~200 MB). Without this, pip pulls the CUDA build (~3 GB) that a
# container without a GPU cannot use. Search on CPU is slower than on the GTX 1650 but works.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
