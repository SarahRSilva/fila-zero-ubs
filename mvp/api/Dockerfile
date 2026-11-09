# Contexto de build: raiz do repositório (a API importa o pacote ia/).
FROM python:3.13-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app
COPY mvp/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ia/__init__.py ia/previsao.py ia/treinar.py ia/triagem.py ia/triagem_llm.py ./ia/
COPY ia/prompts ./ia/prompts
COPY ia/modelo/previsao_demanda.pkl ./ia/modelo/
COPY mvp/api/app ./app
RUN useradd --system --no-create-home api
USER api
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
