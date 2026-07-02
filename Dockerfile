FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MINING_AGENT_OFFLINE=1

COPY pyproject.toml README.md RUN.md ./
COPY src ./src
COPY tests ./tests
COPY examples ./examples
COPY data ./data

RUN python -m pip install --no-cache-dir -U pip \
    && python -m pip install --no-cache-dir -e ".[dev]"

CMD ["python", "-m", "mining_daily_agent.agent", "--topic", "Pilbara lithium mine", "--days", "7"]
