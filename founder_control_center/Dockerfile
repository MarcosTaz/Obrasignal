FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8088 \
    FCC_DB=/data/founder_control_center.db \
    FCC_SECURE_COOKIE=1

WORKDIR /app

RUN addgroup --system fcc && adduser --system --ingroup fcc fcc \
    && mkdir -p /data \
    && chown -R fcc:fcc /data /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY --chown=fcc:fcc founder_control_center /app/founder_control_center

USER fcc
EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8088')+'/health', timeout=3).read()" || exit 1

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 30 --access-logfile - --error-logfile - founder_control_center.wsgi:app"]
