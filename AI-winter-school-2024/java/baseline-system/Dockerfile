# Build the project
FROM maven:3-eclipse-temurin-17 AS build
WORKDIR /app
COPY java/baseline-system/pom.xml pom.xml
RUN mvn dependency:go-offline
COPY java/baseline-system/src src
RUN mvn -Dmaven.test.skip=true package

# Create the container in which we want to run the program
FROM openjdk:17-slim

# Define work directory
WORKDIR /app

# Add the compiled java program
COPY --from=build /app/target/sail-24-ws-baseline.jar .

# Run our component
CMD java -cp sail-24-ws-baseline.jar org.hobbit.core.run.ComponentStarter org.dice_research.hobbit.example.sailws24.BaselineSystem

