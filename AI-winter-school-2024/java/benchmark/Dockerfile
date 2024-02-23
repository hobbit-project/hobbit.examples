# Build the project
FROM maven:3-eclipse-temurin-17 AS build
WORKDIR /app
COPY java/benchmark/pom.xml pom.xml
RUN mvn dependency:go-offline
COPY java/benchmark/src src
RUN mvn -Dmaven.test.skip=true package

# Create the container in which we want to run the program
FROM openjdk:17-slim

# Add the data
ADD data /data

# Define work directory
WORKDIR /app

# Add the compiled java program
COPY --from=build /app/target/ai-ws-2024-benchmark.jar .

# Run our component
CMD java -cp ai-ws-2024-benchmark.jar org.hobbit.core.run.ComponentStarter org.dice_research.hobbit.example.aiws24.BenchmarkController

