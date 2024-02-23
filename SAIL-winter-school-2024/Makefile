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

###################################
# Platform-related commands
###################################

remove-hobbit-containers:
	docker ps -a -q --filter "label=org.hobbit.type" | xargs docker rm -f

create-networks:
	@docker network inspect hobbit >/dev/null || (docker network create -d overlay --attachable --subnet 172.16.100.0/24 hobbit && echo "Created network: hobbit")
	@docker network inspect hobbit-core >/dev/null || (docker network create -d overlay --attachable --subnet 172.16.101.0/24 hobbit-core && echo "Created network: hobbit-core")
	@docker network inspect hobbit-services >/dev/null || (docker network create -d overlay --attachable --subnet 172.16.102.0/24 hobbit-services && echo "Created network: hobbit-services")

start-hobbit-platform:
	docker compose up -d

stop-hobbit-platform:
	docker compose down
