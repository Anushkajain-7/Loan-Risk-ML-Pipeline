FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 loanlens
COPY --chown=loanlens:loanlens app app
COPY --chown=loanlens:loanlens ml ml
COPY --chown=loanlens:loanlens scripts scripts
COPY --chown=loanlens:loanlens frontend frontend
COPY --chown=loanlens:loanlens artifacts artifacts
COPY --chown=loanlens:loanlens reports reports
USER loanlens
EXPOSE 8000
CMD ["python","-m","uvicorn","app.main:create_app","--factory","--host","0.0.0.0","--port","8000","--no-access-log","--no-proxy-headers"]
