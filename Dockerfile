FROM python:3.11-slim-bookworm

WORKDIR /app
COPY requirements-docker.txt .
COPY dist/pollect*.whl .
RUN pip install ./*.whl && \
	pip install -r requirements-docker.txt && \
	rm ./*.whl


ENV PYTHONPATH="${PYTHONPATH}:/pollect"
CMD ["python", "-m", "pollect.Pollect", "--config", "/pollect/config"]