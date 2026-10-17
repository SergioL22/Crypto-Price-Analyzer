FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-backend.txt ./
RUN pip install --no-cache-dir -r requirements-backend.txt && useradd --create-home --uid 10001 appuser
COPY hosted_preview.py stock_service.py stock_provider.py stock_cache.py stock_validation.py stock_models.py assets.py analysis.py api.py data.py history_window.py backend_models.py profile_models.py company_profiles.py price_validation.py ./
COPY static/ ./static/
USER appuser
EXPOSE 10000
# Render is the sole ingress and terminates TLS. One worker preserves process budgets.
CMD ["sh", "-c", "exec python -m uvicorn hosted_preview:create_app --factory --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --proxy-headers --forwarded-allow-ips '*' --no-access-log"]
