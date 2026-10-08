# Smoulder. Each target calls scripts/tasks.py, which also works on Windows: python scripts/tasks.py <target>
PY ?= python

.PHONY: setup gate backfill-local dev test preflight deploy web-deploy demo replay

setup:          ; $(PY) scripts/tasks.py setup
gate:           ; $(PY) scripts/tasks.py gate
backfill-local: ; $(PY) scripts/tasks.py backfill-local
dev:            ; cd web && npm run dev
test:           ; $(PY) scripts/tasks.py test
preflight:      ; $(PY) scripts/tasks.py preflight
deploy:         ; $(PY) scripts/tasks.py deploy
web-deploy:     ; $(PY) scripts/tasks.py web-deploy
demo:           ; $(PY) scripts/tasks.py demo
# make replay DET=<det_id> [SUB=<sub_id>]
replay:         ; $(PY) scripts/tasks.py replay $(DET) $(SUB)
