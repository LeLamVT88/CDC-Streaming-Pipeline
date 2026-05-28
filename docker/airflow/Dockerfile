FROM apache/airflow:2.9.3

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow
COPY airflow/requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
