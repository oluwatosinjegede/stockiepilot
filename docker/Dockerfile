FROM python:3.11

WORKDIR /app
COPY . .

RUN pip install -r requirements/base.txt

CMD ["gunicorn", "config.wsgi:application"]