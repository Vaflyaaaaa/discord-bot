FROM python:3.13

RUN apt-get update && apt-get install -y --fix-missing ffmpeg

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
