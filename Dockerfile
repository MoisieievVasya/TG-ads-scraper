FROM mcr.microsoft.com/playwright/python:v1.52.0-jammy

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN playwright install chromium

CMD ["python", "run.py"]