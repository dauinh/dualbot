FROM python:3.10-bookworm

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["chainlit", "run", "main.py"]