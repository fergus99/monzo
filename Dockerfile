FROM python:3.13-alpine
COPY ./requirements.txt /
WORKDIR /
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]