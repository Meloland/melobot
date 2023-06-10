FROM python:3.9

ADD . /app
WORKDIR /app
RUN pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple
WORKDIR /app/bot
CMD ["python", "main.py"]
