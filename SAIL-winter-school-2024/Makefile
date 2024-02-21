.PHONY: all clean

build: build-java build-python

build-java: build-java-benchmark build-java-system

build-java-benchmark:
	docker build -t sail-ws-2024-java-benchmark -f java/benchmark/Dockerfile .

build-java-system:
	docker build -t sail-ws-2024-java-baseline-system -f java/baseline-system/Dockerfile .

build-python: build-python-benchmark build-python-system

build-python-benchmark:
	docker build -t sail-ws-2024-python-benchmark -f python/benchmark/Dockerfile .

build-python-system:
	docker build -t sail-ws-2024-python-baseline-system -f python/baseline-system/Dockerfile .

remove-hobbit-containers:
	docker rm -f $(docker ps -a -q --filter "label=org.hobbit.type")

start-hobbit-platform:
	docker compose up -d

stop-hobbit-platform:
	docker compose down
