FROM python:3.12.5
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "app.py"]
RUN ls -al /app