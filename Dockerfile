FROM python:3.10-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y python3-venv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv venv
ENV PATH="/app/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y libgl1-mesa-glx libglib2.0-0 tesseract-ocr \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install -r requirements.txt

CMD ["python", "main.py"]
