FROM python:3.13-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir paho-mqtt==2.2.0
COPY mock_sensor.py coletor.py ./
CMD ["python", "coletor.py"]
