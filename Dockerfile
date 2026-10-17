# Multi-arch image: builds natively for linux/s390x (IBM Z / LinuxONE) and linux/amd64.
#   docker buildx build --platform linux/s390x,linux/amd64 -t youthquest-ai .
FROM registry.access.redhat.com/ubi9/python-311
WORKDIR /opt/app-root/src
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY web/ ./web/
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
