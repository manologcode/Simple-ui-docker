FROM python:3.12-slim

RUN apt-get update -y && \
    apt-get install -y curl

ENV TZ Europe/Madrid

WORKDIR /app

RUN python -m pip install --upgrade pip

COPY ./app /app
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 80

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-b", "0.0.0.0:80", "app:app", "--log-level", "info"]
