PI ?= piano-pi
TABLET ?= tab-s6-lite

.PHONY: dev-backend dev-app test deploy logs ssh status tablet-connect tablet-mirror tablet-open

dev-backend:      ## backend on this machine, no piano needed
	cd backend && PC_MIDI_ENABLED=false PC_DATA_DIR=./.devdata uv run piano-companion

dev-app:          ## vite dev server with hot reload; proxies /api to the Pi (override with PI_URL=http://localhost:8000)
	cd app && npm run dev

test:
	cd backend && uv run --extra align ruff check src tests && uv run --extra align pytest -q
	cd app && npm run typecheck && npm test

deploy:
	./deploy/deploy.sh $(PI)

logs:
	ssh $(PI) journalctl -u piano-companion -f

status:
	ssh $(PI) 'systemctl is-active piano-companion; curl -s localhost:8000/api/status; echo; aconnect -i'

ssh:
	ssh $(PI)

# Tablet: one-time pairing is in docs/remote-access.md
tablet-connect:
	adb connect $(TABLET):5555 && adb devices

tablet-mirror:    ## see and control the tablet screen from this machine
	scrcpy --stay-awake --max-size 1600

tablet-open:      ## open the app on the tablet
	adb shell am start -a android.intent.action.VIEW -d "$${APP_URL:-https://piano-pi.$${TAILNET:?set TAILNET}.ts.net}"
