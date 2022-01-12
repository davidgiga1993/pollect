FROM python:3.9-slim-buster

WORKDIR /app
COPY requirements-docker.txt .
COPY dist/pollect*.whl .
RUN pip install *.whl && pip install -r requirements-docker.txt


ENV PYTHONPATH "${PYTHONPATH}:/pollect"
CMD ["python", "-m", "pollect.Pollect", "--config", "/pollect/config.json"]