FROM python:alpine
WORKDIR /app
COPY ./ /app
RUN pip install --upgrade pip setuptools wheel
RUN if [ -f pyproject.toml ]; then \
      pip install .; \
    else \
      echo "No pyproject.toml found - continuing without installing deps" ; \
    fi

# Create non-root user
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1

EXPOSE 5000

# Default command: run gunicorn. The project server.py listens on 0.0.0.0:5000
CMD ["gunicorn", "server:app", "--bind", "0.0.0.0:5000", "--workers", "2", "--worker-class", "gthread"]
