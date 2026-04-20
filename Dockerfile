FROM alpine:latest

RUN apk add --no-cache python3 iproute2

WORKDIR /app

COPY router.py .

CMD ["python3", "-u", "router.py"]