FROM python:3.9-slim

WORKDIR /

COPY . /

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python3", "-m", "flask", "run"]