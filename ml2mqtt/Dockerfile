FROM alpine:3.19

WORKDIR /app

RUN apk add --no-cache py3-scikit-learn py3-flask py3-paho-mqtt inotify-tools

COPY . .
    
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--no-reload"]
