FROM python:3.11-alpine

WORKDIR /code

EXPOSE 8000

ENV IN_DOCKER=true

COPY ./requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r ./requirements.txt

COPY . /code

ENTRYPOINT ["python","xscrap.py"]