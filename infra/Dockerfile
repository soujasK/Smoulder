# Smoulder pipeline + API Lambda image (Python 3.12). Build context: repository root.
FROM public.ecr.aws/lambda/python:3.12
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt && pip install --no-cache-dir --upgrade boto3
COPY pipeline ${LAMBDA_TASK_ROOT}/pipeline
COPY api ${LAMBDA_TASK_ROOT}/api
COPY config ${LAMBDA_TASK_ROOT}/config
COPY data ${LAMBDA_TASK_ROOT}/data
ENV PYTHONUNBUFFERED=1
CMD ["pipeline.aws.tasks.handler"]
